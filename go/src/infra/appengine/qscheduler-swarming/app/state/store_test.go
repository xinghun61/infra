// Copyright 2019 The LUCI Authors.
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

package state

import (
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"

	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/scheduler"
)

func TestSaveLoadList(t *testing.T) {
	Convey("Given a testing context", t, func() {
		ctx := gaetesting.TestingContext()
		// This test (in particular, the GetAll query within List) relies
		// on datastore indexes being up to date after writes. Putting the
		// testing context into Consistent mode ensures that this is always
		// the case.
		datastore.GetTestable(ctx).Consistent(true)

		Convey("when List is called", func() {
			l, err := List(ctx)
			Convey("then nothing is returned.", func() {
				So(l, ShouldBeEmpty)
				So(err, ShouldBeNil)
			})
		})

		Convey("when two Schedulers are saved", func() {
			s1 := NewStore("s1")
			s2 := NewStore("s2")
			t1 := time.Unix(0, 0)
			t2 := time.Unix(1, 0)
			So(s1.Save(ctx, types.NewQScheduler("s1", t1, scheduler.NewConfig())), ShouldBeNil)
			So(s2.Save(ctx, types.NewQScheduler("s2", t2, scheduler.NewConfig())), ShouldBeNil)
			Convey("when Load is called on one", func() {
				l, err := s1.Load(ctx)
				Convey("then it returns the saved value.", func() {
					So(err, ShouldBeNil)
					So(l, ShouldNotBeNil)
				})
			})

			Convey("when List is called", func() {
				l, err := List(ctx)
				Convey("then both scheduler ids are returned.", func() {
					So(err, ShouldBeNil)
					So(l, ShouldHaveLength, 2)
					So(l, ShouldContain, "s1")
					So(l, ShouldContain, "s2")
				})
			})
		})
	})
}
