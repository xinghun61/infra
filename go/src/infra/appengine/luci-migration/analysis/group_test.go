// Copyright 2015 The LUCI Authors.
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
	"testing"
	"time"

	"go.chromium.org/luci/buildbucket"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/data/strpair"

	. "github.com/smartystreets/goconvey/convey"
)

func build(buildset string, duration time.Duration, status buildbucket.Status) *buildbucket.Build {
	return &buildbucket.Build{
		Tags:           strpair.Map{buildbucket.TagBuildSet: []string{buildset}},
		Status:         status,
		CreationTime:   testclock.TestRecentTimeUTC,
		StartTime:      testclock.TestRecentTimeUTC,
		CompletionTime: testclock.TestRecentTimeUTC.Add(duration),
	}
}

func side(duration time.Duration, statuses ...buildbucket.Status) groupSide {
	s := make(groupSide, len(statuses))
	for i, st := range statuses {
		s[i] = build("dummy", duration, st)
	}
	return s
}

func TestGroup(t *testing.T) {
	t.Parallel()

	Convey("Group", t, func() {
		Convey("success", func() {
			So(side(time.Hour, success).success(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeFalse)
		})
		Convey("trustworthy", func() {
			So(side(time.Hour, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeFalse)
		})
		Convey("avgRunDuration", func() {
			s := groupSide{
				build("dummy", 10*time.Minute, success),
				build("dummy", 20*time.Minute, success),
				build("dummy", 30*time.Minute, success),
			}
			So(s.avgRunDuration(), ShouldEqual, 20*time.Minute)
		})
	})
}
