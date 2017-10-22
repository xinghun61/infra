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

	"go.chromium.org/luci/buildbucket"
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
type groupSide []*buildbucket.Build

func (s groupSide) avgRunDuration() time.Duration {
	avg := time.Duration(0)
	count := 0
	for _, b := range s {
		if d, ok := b.RunDuration(); ok {
			avg += d
			count++
		}
	}
	if count == 0 {
		return 0
	}
	return avg / time.Duration(count)
}

// Age returns duration from most recent build completion to now.
func (s groupSide) Age() time.Duration {
	if len(s) == 0 {
		return 0
	}
	return time.Now().Sub(s[len(s)-1].CompletionTime)
}

// success returns true if at least one build succeeded, otherwise false.
func (s groupSide) success() bool {
	for _, b := range s {
		if b.Status == buildbucket.StatusSuccess {
			return true
		}
	}
	return false
}

// trustworthy returns true if s can be used for correctness analysis.
func (s groupSide) trustworthy() bool {
	if s.success() {
		return true
	}

	// If there are no successful builds and fewer than 3 trustworthy failures,
	// consider this result too vulnerable to flakes.
	failures := 0
	for _, b := range s {
		if b.Status == buildbucket.StatusFailure {
			failures++
			if failures >= 3 {
				return true
			}
		}
	}
	return false
}
