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

	"infra/appengine/luci-migration/storage"
)

const (
	// lowSpeed is the lower speed threshold. If speed drops below this,
	// the builder is not WAI
	lowSpeed = 0.8
	// highSpeed is the target speed. If speed is high or more, the builder is
	// WAI.
	highSpeed = 0.9
	// targetHealth is the desired percentage of non-LUCI-only-infra-failing groups (out of total
	// groups). Missing the target is still WAI if the builder is correct and fast enough, but not if
	// the builder is correct but not above highSpeed.
	targetHealth = 0.8
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

	MatchingInfraFailures     []*group
	LUCIOnlyInfraFailures     []*group
	BuildbotOnlyInfraFailures []*group

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

		// Check for Infra Failures. Dedup all of a group's failures into one instance of failing group.
		luciInfraFailed := g.LUCI.countInfraFailures() > 0
		bbInfraFailed := g.Buildbot.countInfraFailures() > 0
		switch {
		case luciInfraFailed && bbInfraFailed:
			comp.MatchingInfraFailures = append(comp.MatchingInfraFailures, g)
		case luciInfraFailed:
			comp.LUCIOnlyInfraFailures = append(comp.LUCIOnlyInfraFailures, g)
		case bbInfraFailed:
			comp.BuildbotOnlyInfraFailures = append(comp.BuildbotOnlyInfraFailures, g)
		}

		if ld, bd := g.LUCI.avgRunDuration(), g.Buildbot.avgRunDuration(); ld > 0 && bd > 0 {
			comp.AvgTimeDelta += ld - bd
			comp.AvgTimeDeltaGroups++
		}
		for _, b := range g.Buildbot {
			avgBuildbotTimeSecs += b.RunDuration.Seconds()
			buildbotBuilds++
		}
	}

	correctnessGroups := comp.CorrectnessGroups()
	switch {
	case avgBuildbotTimeSecs == 0.0:
		comp.Status = storage.StatusNoData
		comp.StatusReason = "Buildbot avg duration is 0"
		return comp
	case comp.TotalGroups == 0:
		comp.Status = storage.StatusNoData
		comp.StatusReason = "No LUCI builds found for comparison"
		return comp
	}
	if correctnessGroups > 0 {
		badGroups := len(comp.FalseSuccesses) + len(comp.FalseFailures)
		comp.Correctness = 1.0 - float64(badGroups)/float64(correctnessGroups)
	}

	if comp.AvgTimeDeltaGroups > 0 {
		avgBuildbotTimeSecs /= float64(buildbotBuilds)
		comp.AvgTimeDelta /= time.Duration(comp.AvgTimeDeltaGroups)
		buildbotSpeed := 1.0 / avgBuildbotTimeSecs
		luciSpeed := 1.0 / (avgBuildbotTimeSecs + comp.AvgTimeDelta.Seconds())
		comp.Speed = luciSpeed / buildbotSpeed
	}

	comp.InfraHealth = 1.0 - float64(len(comp.LUCIOnlyInfraFailures))/float64(comp.TotalGroups)

	switch {
	case correctnessGroups < minCorrectnessGroups:
		// Collect available data but indicate low confidence.
		comp.Status = storage.StatusLowConfidence
		comp.StatusReason = ("Insufficient LUCI and Buildbot builds that " +
			"share same patchsets and can be used for correctness estimation")
	case comp.Correctness < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Incorrect"
	case comp.Speed < lowSpeed:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too slow; want at least 90% speed"
	case comp.InfraHealth < targetHealth:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too many new infra failures"
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
