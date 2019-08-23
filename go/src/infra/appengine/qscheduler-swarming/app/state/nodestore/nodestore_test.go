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
	"go.chromium.org/luci/appengine/gaetesting"

	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/scheduler"
)

type createUniqueAccount struct{}

// createUniqueAccount implements nodestore.Operator
var _ nodestore.Operator = createUniqueAccount{}

func (n createUniqueAccount) Modify(ctx context.Context, s *types.QScheduler) error {
	s.Scheduler.AddAccount(ctx, scheduler.AccountID(uuid.New().String()), scheduler.NewAccountConfig(0, 0, nil, false), nil)
	return nil
}

func (n createUniqueAccount) Commit(_ context.Context) error {
	return nil
}

func (n createUniqueAccount) Finish(_ context.Context) {}

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
			err = store.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			err = store.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			err = store.Run(ctx, createUniqueAccount{})
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
			err = storeA.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			err = storeB.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			err = storeA.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			err = storeB.Run(ctx, createUniqueAccount{})
			So(err, ShouldBeNil)

			s, err := storeA.Get(ctx)
			So(err, ShouldBeNil)
			So(len(s.Scheduler.Config().AccountConfigs), ShouldEqual, 4)
		})
	})
}
