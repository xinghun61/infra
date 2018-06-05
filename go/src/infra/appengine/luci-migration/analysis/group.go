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
	"fmt"
	"time"

	"go.chromium.org/luci/buildbucket/proto"
)

type groupKey struct {
	// do not put interfaces in this struct,
	// because it is used as a map key.
	Host        string
	Change      int64
	Patchset    int64
	GotRevision string
}

func (k *groupKey) GerritChange() *buildbucketpb.GerritChange {
	return &buildbucketpb.GerritChange{
		Host:     k.Host,
		Change:   k.Change,
		Patchset: k.Patchset,
	}
}

func (k *groupKey) String() string {
	return fmt.Sprintf("%s @ %q", k.GerritChange().BuildSetString(), k.GotRevision)
}

// group is two sets of builds, for Buildbot and LUCI, that should have the same
// results.
type group struct {
	Key            groupKey
	LUCI, Buildbot groupSide
}

// trustworthy returns true if g can be used for correctness analysis.
func (g *group) trustworthy() bool {
	return g.Buildbot.trustworthy() && g.LUCI.trustworthy()
}

// build contains minimal information needed for analysis.
type build struct {
	Status         buildbucketpb.Status
	CreationTime   time.Time
	CompletionTime time.Time
	RunDuration    time.Duration
	URL            string
}

// groupSide is a list of builds ordered from oldest to newest
type groupSide []*build

func (s groupSide) avgRunDuration() time.Duration {
	avg := time.Duration(0)
	count := 0
	for _, b := range s {
		avg += b.RunDuration
		count++
	}
	if count == 0 {
		return 0
	}
	return avg / time.Duration(count)
}

// MostRecentlyCompleted returns completion time of the most recently created
// build.
func (s groupSide) MostRecentlyCompleted() time.Time {
	if len(s) == 0 {
		return time.Time{}
	}
	return s[len(s)-1].CompletionTime
}

// success returns true if at least one build succeeded, otherwise false.
func (s groupSide) success() bool {
	for _, b := range s {
		if b.Status == buildbucketpb.Status_SUCCESS {
			return true
		}
	}
	return false
}

// countInfraFailures returns number of builds that Infra Failed.
func (s groupSide) countInfraFailures() int {
	count := 0
	for _, b := range s {
		if b.Status == buildbucketpb.Status_INFRA_FAILURE {
			count++
		}
	}
	return count
}

// trustworthy returns true if s can be used for correctness analysis.
func (s groupSide) trustworthy() bool {
	if s.success() {
		return true
	}

	// If there are no successful builds and fewer than 2 trustworthy failures,
	// consider this result too vulnerable to flakes.
	failures := 0
	for _, b := range s {
		if b.Status == buildbucketpb.Status_FAILURE {
			failures++
			if failures >= 2 {
				return true
			}
		}
	}

	return false
}
