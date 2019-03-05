// Copyright 2018 The LUCI Authors.
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

package inventory

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
	"testing"
	"time"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/proto/google"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestGetDutInfoWithConsistentDatastore(t *testing.T) {
	Convey("On happy path and a single DUT in the inventory", t, func() {
		ctx := testingContext()
		ctx = setDutInfoCacheValidity(ctx, 100*time.Minute)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{id: "dut1_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
		})

		Convey("initial GetDutInfo (by Id) returns NotFound", func() {
			_, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_id"})
			So(status.Code(err), ShouldEqual, codes.NotFound)
		})

		Convey("initial GetDutInfo (by Hostname) returns NotFound", func() {
			_, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Hostname: "dut1_hostname"})
			So(status.Code(err), ShouldEqual, codes.NotFound)
		})

		Convey("initial GetDutInfo without args returns InvalidArgument", func() {
			_, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{})
			So(status.Code(err), ShouldEqual, codes.InvalidArgument)
		})

		Convey("after a call to UpdateCachedInventory", func() {
			_, err := tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
			So(err, ShouldBeNil)

			Convey("GetDutInfo (by ID) returns the DUT", func() {
				resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_id"})
				So(err, ShouldBeNil)
				dut := getDutInfo(t, resp)
				So(dut.GetCommon().GetId(), ShouldEqual, "dut1_id")
				So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_hostname")
			})

			Convey("GetDutInfo (by Hostname) returns the DUT", func() {
				resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Hostname: "dut1_hostname"})
				So(err, ShouldBeNil)
				dut := getDutInfo(t, resp)
				So(dut.GetCommon().GetId(), ShouldEqual, "dut1_id")
				So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_hostname")
			})

			Convey("after an ID update, GetDutInfo (by Hostname) returns updated DUT", func() {
				setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
					{id: "dut1_new_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
				})
				_, err := tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
				So(err, ShouldBeNil)

				resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Hostname: "dut1_hostname"})
				So(err, ShouldBeNil)
				dut := getDutInfo(t, resp)
				So(dut.GetCommon().GetId(), ShouldEqual, "dut1_new_id")
				So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_hostname")
			})
		})
	})
}

func TestGetDutInfoWithConsistentDatastoreNoCacheValidity(t *testing.T) {
	Convey("With no cache validity a single DUT in the inventory", t, func() {
		ctx := testingContext()
		ctx = setDutInfoCacheValidity(ctx, 0*time.Second)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{id: "dut1_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
		})

		Convey("after a call to UpdateCachedInventory", func() {
			_, err := tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
			So(err, ShouldBeNil)

			Convey("GetDutInfo (by ID) returns NotFound", func() {
				// Cache is already invalid, so DUT can't be found.
				_, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_id"})
				So(status.Code(err), ShouldEqual, codes.NotFound)
			})
		})
	})
}

func TestGetDutInfoWithEventuallyConsistentDatastore(t *testing.T) {
	Convey("With eventually consistent datastore and a single DUT in the inventory", t, func() {
		ctx := testingContext()
		ctx = setDutInfoCacheValidity(ctx, 100*time.Second)
		datastore.GetTestable(ctx).Consistent(false)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{id: "dut1_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
		})

		Convey("after a call to UpdateCachedInventory", func() {
			_, err := tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
			So(err, ShouldBeNil)

			Convey("GetDutInfo (by ID) returns the DUT", func() {
				resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_id"})
				So(err, ShouldBeNil)
				dut := getDutInfo(t, resp)
				So(dut.GetCommon().GetId(), ShouldEqual, "dut1_id")
				So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_hostname")
			})

			Convey("GetDutInfo (by Hostname) returns NotFound", func() {
				_, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_hostname"})
				So(status.Code(err), ShouldEqual, codes.NotFound)
			})

			Convey("after index update, GetDutInfo (by Hostname) returns the DUT", func() {
				datastore.GetTestable(ctx).CatchupIndexes()
				resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Hostname: "dut1_hostname"})
				So(err, ShouldBeNil)
				dut := getDutInfo(t, resp)
				So(dut.GetCommon().GetId(), ShouldEqual, "dut1_id")
				So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_hostname")

				Convey("after a Hostname update, GetDutInfo (by Hostname) returns NotFound", func() {
					setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
						{id: "dut1_id", hostname: "dut1_new_hostname", model: "link", pool: "DUT_POOL_SUITES"},
					})
					_, err := tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
					So(err, ShouldBeNil)

					_, err = tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Id: "dut1_hostname"})
					So(status.Code(err), ShouldEqual, codes.NotFound)

					Convey("after index update, GetDutInfo (by Hostname) returns the DUT for the new Hostname", func() {
						datastore.GetTestable(ctx).CatchupIndexes()
						resp, err := tf.Inventory.GetDutInfo(tf.C, &fleet.GetDutInfoRequest{Hostname: "dut1_new_hostname"})
						So(err, ShouldBeNil)
						dut := getDutInfo(t, resp)
						So(dut.GetCommon().GetId(), ShouldEqual, "dut1_id")
						So(dut.GetCommon().GetHostname(), ShouldEqual, "dut1_new_hostname")
					})
				})
			})
		})
	})
}

func setDutInfoCacheValidity(ctx context.Context, v time.Duration) context.Context {
	cfg := config.Get(ctx)
	cfg.Inventory.DutInfoCacheValidity = google.NewDuration(v)
	return config.Use(ctx, cfg)
}
func getDutInfo(t *testing.T, di *fleet.GetDutInfoResponse) *inventory.DeviceUnderTest {
	t.Helper()

	var dut inventory.DeviceUnderTest
	So(di.Spec, ShouldNotBeNil)
	err := proto.Unmarshal(di.Spec, &dut)
	So(err, ShouldBeNil)
	return &dut
}
