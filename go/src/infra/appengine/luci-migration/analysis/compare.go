// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package analysis

import (
	"time"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/storage"
)

const (
	// lowSpeed is the lower speed threshold. If speed drops below this,
	// the builder is not WAI
	lowSpeed = 0.8
	// highSpeed is the target speed. If speed is high or more, the builder is
	// WAI.
	highSpeed = 0.9
)

// This file is the heart of this package.
// We anticipate this code to get smarter as we discover new patterns of flakes.

// diff is a result of comparison of LUCI and Buildbot tryjobs.
// It is produced by compare and consumed by tmplDetails.
type diff struct {
	MinBuildAge time.Duration

	storage.BuilderMigration
	StatusReason string

	TotalGroups int

	ConsistentGroups []*group
	FalseFailures    []*group
	FalseSuccesses   []*group

	AvgTimeDeltaGroups int
	AvgTimeDelta       time.Duration // Average overhead of LUCI across patchsets.
}

func (d *diff) CorrectnessGroups() int {
	return len(d.ConsistentGroups) + len(d.FalseFailures) + len(d.FalseSuccesses)
}

func (d *diff) RejectedCorrectnessGroups() int {
	return d.TotalGroups - d.CorrectnessGroups()
}

// compare compares Buildbot and LUCI builds within groups.
func compare(groups []*group, minCorrectnessGroups int, currentStatus storage.MigrationStatus) *diff {
	comp := &diff{
		BuilderMigration: storage.BuilderMigration{AnalysisTime: time.Now().UTC()},
		TotalGroups:      len(groups),
	}

	buildbotBuilds := 0
	avgBuildbotTimeSecs := 0.0
	for _, g := range groups {
		if g.trustworthy() {
			switch luciSuccess := g.LUCI.success(); {
			case luciSuccess == g.Buildbot.success():
				comp.ConsistentGroups = append(comp.ConsistentGroups, g)
			case luciSuccess:
				comp.FalseSuccesses = append(comp.FalseSuccesses, g)
			default:
				comp.FalseFailures = append(comp.FalseFailures, g)
			}
		}

		if ld, bd := g.LUCI.avgRunDuration(), g.Buildbot.avgRunDuration(); ld > 0 && bd > 0 {
			comp.AvgTimeDelta += ld - bd
			comp.AvgTimeDeltaGroups++
		}
		for _, b := range g.Buildbot {
			if d := bbutil.RunDuration(b); d > 0 {
				avgBuildbotTimeSecs += d.Seconds()
				buildbotBuilds++
			}
		}
	}

	correctnessGroups := comp.CorrectnessGroups()
	if correctnessGroups == 0 || correctnessGroups < minCorrectnessGroups {
		comp.Status = storage.StatusInsufficientData
		comp.StatusReason = ("Insufficient LUCI and Buildbot builds that " +
			"share same patchsets and can be used for correctness estimation")
		return comp
	}
	if avgBuildbotTimeSecs == 0.0 {
		comp.Status = storage.StatusInsufficientData
		comp.StatusReason = "Buildbot avg duration is 0"
		return comp
	}
	badGroups := len(comp.FalseSuccesses) + len(comp.FalseFailures)
	comp.Correctness = 1.0 - float64(badGroups)/float64(correctnessGroups)

	avgBuildbotTimeSecs /= float64(buildbotBuilds)
	comp.AvgTimeDelta /= time.Duration(comp.AvgTimeDeltaGroups)
	buildbotSpeed := 1.0 / avgBuildbotTimeSecs
	luciSpeed := 1.0 / (avgBuildbotTimeSecs + comp.AvgTimeDelta.Seconds())
	comp.Speed = luciSpeed / buildbotSpeed

	switch {
	case comp.Correctness < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Incorrect"
	case comp.Speed < lowSpeed:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too slow; want at least 90% speed"
	case comp.Speed >= highSpeed:
		comp.Status = storage.StatusLUCIWAI
		comp.StatusReason = "Correct and fast enough"
	// the speed is between low and high
	case currentStatus == storage.StatusLUCIWAI:
		// leave as WAI. It is not too bad.
		comp.Status = storage.StatusLUCIWAI
		comp.StatusReason = "Correct and fast enough; speed is fluctuating"
	default:
		// same as case comp.Speed < lowSpeed,
		// separated for simplicity of switch statement.
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too slow; want at least 90% speed"
	}
	return comp
}
