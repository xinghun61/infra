// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package analysis

import (
	"time"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/storage"
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

	CorrectnessGroups int
	FalseFailures     []*group
	FalseSuccesses    []*group

	AvgTimeDeltaGroups int
	AvgTimeDelta       time.Duration // Average overhead of LUCI across patchsets.
}

func (d *diff) RejectedCorrectnessGroups() int {
	return d.TotalGroups - d.CorrectnessGroups
}

// compare compares Buildbot and LUCI builds within groups.
func compare(groups []*group, minCorrectnessGroups int) *diff {
	comp := &diff{
		BuilderMigration: storage.BuilderMigration{AnalysisTime: time.Now().UTC()},
		TotalGroups:      len(groups),
	}

	buildbotBuilds := 0
	avgBuildbotTimeSecs := 0.0
	for _, g := range groups {
		if g.trustworthy() {
			comp.CorrectnessGroups++
			if luciSuccess := g.LUCI.success(); luciSuccess != g.Buildbot.success() {
				if luciSuccess {
					comp.FalseSuccesses = append(comp.FalseSuccesses, g)
				} else {
					comp.FalseFailures = append(comp.FalseFailures, g)
				}
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

	if comp.CorrectnessGroups == 0 || comp.CorrectnessGroups < minCorrectnessGroups {
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
	comp.Correctness = 1.0 - float64(badGroups)/float64(comp.CorrectnessGroups)

	avgBuildbotTimeSecs /= float64(buildbotBuilds)
	comp.AvgTimeDelta /= time.Duration(comp.AvgTimeDeltaGroups)
	buildbotSpeed := 1.0 / avgBuildbotTimeSecs
	luciSpeed := 1.0 / (avgBuildbotTimeSecs + comp.AvgTimeDelta.Seconds())
	comp.Speed = luciSpeed / buildbotSpeed

	switch {
	case comp.Correctness < 1.0:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Incorrect"
	case comp.Speed < 0.9:
		comp.Status = storage.StatusLUCINotWAI
		comp.StatusReason = "Too slow"
	default:
		comp.Status = storage.StatusLUCIWAI
		comp.StatusReason = "Correct and fast enough"
	}
	return comp
}
