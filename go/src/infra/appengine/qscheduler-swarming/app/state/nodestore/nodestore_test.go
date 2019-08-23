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

package nodestore_test

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"

	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/scheduler"
)

type createUniqueAccounts struct {
	count int
}

// createUniqueAccount implements nodestore.Operator
var _ nodestore.Operator = createUniqueAccounts{}

func (n createUniqueAccounts) Modify(ctx context.Context, s *types.QScheduler) error {
	for i := 0; i < n.count; i++ {
		s.Scheduler.AddAccount(ctx, scheduler.AccountID(uuid.New().String()), scheduler.NewAccountConfig(0, 0, nil, false), nil)
	}
	return nil
}

func (n createUniqueAccounts) Commit(_ context.Context) error {
	return nil
}

func (n createUniqueAccounts) Finish(_ context.Context) {}

func addDatastoreIndexes(ctx context.Context) error {
	defs, err := datastore.FindAndParseIndexYAML(".")
	if err != nil {
		return err
	}
	datastore.GetTestable(ctx).AddIndexes(defs...)
	return nil
}

func TestBasicRun(t *testing.T) {
	Convey("Given a testing context with a created entity", t, func() {
		ctx := gaetesting.TestingContext()

		store := nodestore.New("foo-pool")
		err := store.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		Convey("duplicate creation attempts fail.", func() {
			err := store.Create(ctx, time.Now())
			So(err, ShouldNotBeNil)
		})

		Convey("operations run without error.", func() {
			err = store.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			err = store.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			err = store.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			s, err := store.Get(ctx)
			So(err, ShouldBeNil)
			So(len(s.Scheduler.Config().AccountConfigs), ShouldEqual, 3)
		})
	})
}

// TestConflictingRun tests that two stores being used concurrently for the same
// qscheduler do not obliterate eachothers' writes.
func TestConflictingRun(t *testing.T) {
	Convey("Given a testing context with a created entity and two stores using it", t, func() {
		ctx := gaetesting.TestingContext()

		storeA := nodestore.New("foo-pool")
		err := storeA.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		storeB := nodestore.New("foo-pool")

		Convey("alternating null operations between both stores run without error.", func() {
			err = storeA.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			err = storeB.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			err = storeA.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			err = storeB.Run(ctx, createUniqueAccounts{1})
			So(err, ShouldBeNil)

			s, err := storeA.Get(ctx)
			So(err, ShouldBeNil)
			So(len(s.Scheduler.Config().AccountConfigs), ShouldEqual, 4)
		})
	})
}

func TestClean(t *testing.T) {
	Convey("Given a testing context with a created entity", t, func() {
		ctx := gaetesting.TestingContext()
		datastore.GetTestable(ctx).Consistent(true)
		err := addDatastoreIndexes(ctx)
		So(err, ShouldBeNil)

		store := nodestore.New("foo-pool")
		err = store.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		Convey("an immediate clean should run without error.", func() {
			count, err := store.Clean(ctx)
			So(count, ShouldEqual, 0)
			So(err, ShouldBeNil)
		})

		Convey("a clean after some operations runs without error, removes stale entities, and does not affect state.", func() {
			for i := 0; i < 200; i++ {
				store.Run(ctx, createUniqueAccounts{1})
				if err != nil {
					// This assert is guarded because we don't want to goconvey
					// to think we did 200 real asserts; that would pollute the UI.
					So(err, ShouldBeNil)
				}
			}

			beforeClean, err := store.Get(ctx)
			So(err, ShouldBeNil)

			count, err := datastore.Count(ctx, datastore.NewQuery("stateNode"))
			So(count, ShouldEqual, 201)

			delCount, err := store.Clean(ctx)
			So(err, ShouldBeNil)
			So(delCount, ShouldEqual, 100)
			afterClean, err := store.Get(ctx)
			So(err, ShouldBeNil)
			So(afterClean, ShouldResemble, beforeClean)

			count, err = datastore.Count(ctx, datastore.NewQuery("stateNode"))
			So(count, ShouldEqual, 101)
		})
	})
}

func TestLargeState(t *testing.T) {
	Convey("Given a testing context with a created entity", t, func() {
		ctx := gaetesting.TestingContext()
		datastore.GetTestable(ctx).Consistent(true)

		store := nodestore.New("foo-pool")
		err := store.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		Convey("a very large state spanning 10 child nodes can be stored.", func() {
			// Given uuid size, 70k accounts causes state to be large enough to
			// be spread over 10 nodes.
			nAccounts := 70 * 1000
			err := store.Run(ctx, createUniqueAccounts{nAccounts})
			So(err, ShouldBeNil)

			state, err := store.Get(ctx)
			So(err, ShouldBeNil)
			So(len(state.Scheduler.Config().AccountConfigs), ShouldEqual, nAccounts)

			count, err := datastore.Count(ctx, datastore.NewQuery("stateNode"))
			// 1 node for generation 0; 10 for generation 1.
			So(count, ShouldEqual, 11)
		})
	})
}

func TestCreateListDelete(t *testing.T) {
	Convey("Given a testing context with a two created entities, List and Delete should work as expected.", t, func() {
		ctx := gaetesting.TestingContext()
		datastore.GetTestable(ctx).Consistent(true)

		storeA := nodestore.New("A")
		err := storeA.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		storeB := nodestore.New("B")
		err = storeB.Create(ctx, time.Now())
		So(err, ShouldBeNil)

		IDs, err := nodestore.List(ctx)
		So(err, ShouldBeNil)
		So(IDs, ShouldHaveLength, 2)
		So(IDs, ShouldContain, "A")
		So(IDs, ShouldContain, "B")

		err = storeB.Delete(ctx)
		So(err, ShouldBeNil)

		IDs, err = nodestore.List(ctx)
		So(err, ShouldBeNil)
		So(IDs, ShouldHaveLength, 1)
		So(IDs, ShouldContain, "A")

		err = storeA.Delete(ctx)
		So(err, ShouldBeNil)

		IDs, err = nodestore.List(ctx)
		So(err, ShouldBeNil)
		So(IDs, ShouldBeEmpty)
	})
}
