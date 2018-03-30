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

	"go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

func side(duration time.Duration, statuses ...buildbucketpb.Status) groupSide {
	s := make(groupSide, len(statuses))
	for i, st := range statuses {
		s[i] = &build{
			Status:         st,
			CreationTime:   testclock.TestRecentTimeUTC,
			CompletionTime: testclock.TestRecentTimeUTC.Add(duration),
			RunDuration:    duration,
		}
	}
	return s
}

func TestGroup(t *testing.T) {
	t.Parallel()

	Convey("Group", t, func() {
		Convey("success", func() {
			So(side(time.Hour, success).success(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, infraFailure, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, infraFailure).trustworthy(), ShouldBeFalse)
		})
		Convey("trustworthy", func() {
			So(side(time.Hour, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, success).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, failure).trustworthy(), ShouldBeTrue)
			So(side(time.Hour, failure, infraFailure).trustworthy(), ShouldBeFalse)
		})
		Convey("avgRunDuration", func() {
			var s groupSide
			for i := 1; i <= 3; i++ {
				duration := time.Duration(i) * 10 * time.Minute
				s = append(s, &build{
					Status:         buildbucketpb.Status_SUCCESS,
					CreationTime:   testclock.TestRecentTimeUTC,
					CompletionTime: testclock.TestRecentTimeUTC.Add(duration),
					RunDuration:    duration,
				})
			}
			So(s.avgRunDuration(), ShouldEqual, 20*time.Minute)
		})
	})
}
