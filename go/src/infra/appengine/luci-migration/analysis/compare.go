// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package analysis

import (
	"fmt"
	"time"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/storage"
)

// This file is the heart of this package.
// We anticipate this code to get smarter as we discover new patterns of flakes.

// diff is a result of comparison of LUCI and Buildbot tryjobs.
// It is produced by compare and consumed by tmplDetails.
type diff struct {
	storage.BuilderMigration
	StatusReason         string
	TotalGroups          int
	TrustworthyGroups    int
	FalseFailures        []*group
	FalseSuccesses       []*group
	AvgTimeDelta         time.Duration // Average overhead of LUCI across patchsets.
	MinBuildCreationDate time.Time
}

func (d *diff) UntrustworthyGroups() int {
	return d.TotalGroups - d.TrustworthyGroups
}

// compare compares Buildbot and LUCI builds within groups.
func compare(groups []*group, minTrustworthyGroups int) *diff {
	comp := &diff{
		BuilderMigration: storage.BuilderMigration{AnalysisTime: time.Now().UTC()},
		TotalGroups:      len(groups),
	}

	buildbotBuilds := 0
	avgBuildbotTimeSecs := 0.0
	for _, g := range groups {
		if g.trustworthy() {
			comp.TrustworthyGroups++
			if luciSuccess := g.LUCI.success(); luciSuccess != g.Buildbot.success() {
				if luciSuccess {
					comp.FalseSuccesses = append(comp.FalseSuccesses, g)
				} else {
					comp.FalseFailures = append(comp.FalseFailures, g)
				}
			}
		}

		comp.AvgTimeDelta += g.LUCI.avgDuration() - g.Buildbot.avgDuration()
		buildbotBuilds += len(g.Buildbot)
		for _, b := range g.Buildbot {
			avgBuildbotTimeSecs += bbutil.Duration(b).Seconds()
		}
	}

	if comp.TrustworthyGroups == 0 || comp.TrustworthyGroups < minTrustworthyGroups {
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
	comp.Correctness = 1.0 - float64(badGroups)/float64(comp.TrustworthyGroups)
	comp.CorrectnessConfidence = float64(comp.TrustworthyGroups) / float64(comp.TotalGroups)

	avgBuildbotTimeSecs /= float64(buildbotBuilds)
	comp.AvgTimeDelta /= time.Duration(comp.TotalGroups)
	buildbotSpeed := 1.0 / avgBuildbotTimeSecs
	luciSpeed := 1.0 / (avgBuildbotTimeSecs + comp.AvgTimeDelta.Seconds())
	comp.Speed = luciSpeed / buildbotSpeed

	switch {
	case comp.Correctness >= 1.0 && comp.Speed >= 1.0:
		comp.Status = storage.StatusLUCIWAI
		comp.StatusReason = "Correct and fast enough"
	case comp.Correctness < 1.0 && comp.Speed < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Incorrect and too slow"
	case comp.Correctness < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Incorrect"
	case comp.Speed < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too slow"
	default:
		panic(fmt.Sprintf("impossible. correctness %f, speed %f", comp.Correctness, comp.Speed))
	}
	return comp
}
