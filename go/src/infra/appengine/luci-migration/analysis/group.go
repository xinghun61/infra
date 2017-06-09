// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package analysis

import (
	"time"

	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"

	"infra/appengine/luci-migration/bbutil"
)

// group is two sets of builds, for Buildbot and LUCI, that should have the same
// results.
// For tryserver, a group is defined by a patchset.
type group struct {
	// Key is the key that was used for grouping.
	// For a tryserver, it is the value of "buildset" tag which identifies a
	// patchset, e.g. "patch/gerrit/chromium-review.googlesource.com/514342/6"
	Key string
	// KeyURL is human-consumable URL for the key, if applicable.
	// For a tryserver, it is a patchset URL.
	KeyURL         string
	LUCI, Buildbot groupSide
}

// trustworthy returns true if g can be used for correctness analysis.
func (g *group) trustworthy() bool {
	return g.Buildbot.trustworthy() && g.LUCI.trustworthy()
}

// groupSide is a list of builds ordered from oldest to newest
type groupSide []*buildbucket.ApiCommonBuildMessage

func (s groupSide) avgDuration() time.Duration {
	if len(s) == 0 {
		return 0
	}
	avg := time.Duration(0)
	for _, b := range s {
		avg += bbutil.Duration(b)
	}
	return avg / time.Duration(len(s))
}

// Age returns duration from most recent build completion to now.
func (s groupSide) Age() time.Duration {
	if len(s) == 0 {
		return 0
	}
	return time.Now().Sub(bbutil.ParseTimestamp(s[len(s)-1].CompletedTs))
}

// success returns true if at least one build succeeded, otherwise false.
func (s groupSide) success() bool {
	for _, b := range s {
		if b.Result == bbutil.ResultSuccess {
			return true
		}
	}
	return false
}

// trustworthy returns true if s can be used for analysis.
func (s groupSide) trustworthy() bool {
	// If there are no successful builds and less than 3 builds,
	// consider this result too vulnerable to flakes.
	return s.success() || len(s) >= 3
}

func (s groupSide) reverse() {
	for i := 0; i < len(s)/2; i++ {
		s[i], s[len(s)-1-i] = s[len(s)-1-i], s[i]
	}
}
