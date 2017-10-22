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
	"io/ioutil"
	"testing"
	"time"

	"go.chromium.org/luci/buildbucket"

	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

const success = buildbucket.StatusSuccess
const failure = buildbucket.StatusFailure

func TestCompare(t *testing.T) {
	t.Parallel()

	Convey("compare", t, func() {
		currentStatus := storage.StatusLUCINotWAI
		compareAndRender := func(groups ...*group) *diff {
			comp := compare(groups, 0, currentStatus)
			// assert renders
			comp.MinBuildAge = time.Hour * 24 * 7
			So(tmplDetails.Execute(ioutil.Discard, comp), ShouldBeNil)
			return comp
		}

		Convey("not enough correctness groups", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(time.Hour, failure, success),
					LUCI:     side(time.Hour, failure, failure),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusInsufficientData)
		})
		Convey("avg buildbot time is 0", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(0, failure, success),
					LUCI:     side(time.Hour, failure, failure),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusInsufficientData)
		})
		Convey("LUCI is incorrect", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(time.Hour, failure, success),
					LUCI:     side(time.Hour, failure, failure, failure),
				},
				&group{
					Key:      "set2",
					Buildbot: side(time.Hour, failure, failure, failure),
					LUCI:     side(time.Hour, success, success),
				},
				&group{
					Key:      "set3",
					Buildbot: side(time.Hour, success),
					LUCI:     side(time.Hour, success),
				},
				&group{
					Key:      "set4",
					Buildbot: side(time.Hour, failure, failure, failure),
					LUCI:     side(time.Hour, failure, failure, failure),
				},
				&group{
					Key:      "set4",
					Buildbot: side(time.Hour, failure, failure, failure),
					LUCI:     side(time.Hour, failure),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusLUCINotWAI)
			So(comp.StatusReason, ShouldEqual, "Incorrect")
			So(comp.Correctness, ShouldAlmostEqual, 0.5)
			So(comp.TotalGroups, ShouldEqual, 5)
			So(comp.CorrectnessGroups(), ShouldEqual, 4)
			So(comp.FalseFailures, ShouldHaveLength, 1)
			So(comp.FalseFailures[0].Key, ShouldEqual, "set1")
			So(comp.FalseSuccesses, ShouldHaveLength, 1)
			So(comp.FalseSuccesses[0].Key, ShouldEqual, "set2")
		})

		Convey("LUCI is correct", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(time.Hour, success),
					LUCI:     side(time.Hour, failure, success),
				},
				&group{
					Key:      "set2",
					Buildbot: side(time.Hour, failure, failure, failure, failure),
					LUCI:     side(time.Hour, failure, failure, failure),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusLUCIWAI)
			So(comp.Correctness, ShouldAlmostEqual, 1)
		})

		Convey("LUCI speed increased, but not too high", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(120*time.Minute, success),
				},
				&group{
					Key:      "set2",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(120*time.Minute, success),
				},
			)
			So(comp.Speed, ShouldBeBetween, lowSpeed, highSpeed)
			So(comp.Status, ShouldEqual, storage.StatusLUCINotWAI)
			So(comp.Speed, ShouldBeGreaterThan, lowSpeed)
		})

		Convey("LUCI is fast", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(90*time.Minute, success),
				},
				&group{
					Key:      "set2",
					Buildbot: side(100*time.Minute, failure, failure, failure),
					LUCI:     side(90*time.Minute, failure, failure, failure),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusLUCIWAI)
			So(comp.StatusReason, ShouldEqual, "Correct and fast enough")
			So(comp.AvgTimeDelta, ShouldAlmostEqual, -10*time.Minute) // 10 min faster
			So(comp.Speed, ShouldBeGreaterThanOrEqualTo, highSpeed)
		})

		Convey("LUCI speed dropped, but not too low", func() {
			currentStatus = storage.StatusLUCIWAI
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(120*time.Minute, success),
				},
				&group{
					Key:      "set2",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(120*time.Minute, success),
				},
			)
			So(comp.Speed, ShouldBeBetween, lowSpeed, highSpeed)
			So(comp.Status, ShouldEqual, storage.StatusLUCIWAI)
		})

		Convey("LUCI is slow", func() {
			comp := compareAndRender(
				&group{
					Key:      "set1",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(150*time.Minute, success),
				},
				&group{
					Key:      "set2",
					Buildbot: side(100*time.Minute, success),
					LUCI:     side(150*time.Minute, success),
				},
			)
			So(comp.Status, ShouldEqual, storage.StatusLUCINotWAI)
			So(comp.AvgTimeDelta, ShouldAlmostEqual, 50*time.Minute)
			So(comp.Speed, ShouldBeLessThan, lowSpeed)
		})
	})
}
