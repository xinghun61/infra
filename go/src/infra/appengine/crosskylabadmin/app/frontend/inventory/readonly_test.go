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
	"testing"
	"time"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/dronecfg"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/freeduts"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/libs/skylab/inventory"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/kylelemons/godebug/pretty"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/common/retry"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

func TestInvalidDutID(t *testing.T) {
	Convey("DutID with empty hostname won't go to drone config datastore", t, func() {
		ctx := testingContext()
		ctx = withDutInfoCacheValidity(ctx, 100*time.Minute)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut1_id", "dut1_hostname", "link", "DUT_POOL_SUITES"},
			}),
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname:    "fake-drone.google.com",
					environment: inventory.Environment_ENVIRONMENT_STAGING,
					dutIDs:      []string{"dut1_id", "empty_id"},
				},
			}),
		})
		So(err, ShouldBeNil)

		_, err = tf.Inventory.UpdateCachedInventory(tf.C, &fleet.UpdateCachedInventoryRequest{})
		So(err, ShouldBeNil)
		e, err := dronecfg.Get(tf.C, "fake-drone.google.com")
		So(err, ShouldBeNil)
		So(e.DUTs, ShouldHaveLength, 1)
		duts := make([]string, len(e.DUTs))
		for i, d := range e.DUTs {
			duts[i] = d.Hostname
		}
		So(duts, ShouldResemble, []string{"dut1_hostname"})
	})
}

func TestListRemovedDuts(t *testing.T) {
	t.Parallel()
	t.Run("no duts added", func(t *testing.T) {
		t.Parallel()
		ctx := gaetesting.TestingContextWithAppID("some-app")
		var is ServerImpl
		resp, err := is.ListRemovedDuts(ctx, &fleet.ListRemovedDutsRequest{})
		if err != nil {
			t.Fatalf("ListRemovedDuts returned error: %s", err)
		}
		if len(resp.Duts) != 0 {
			t.Errorf("Got %#v; expected empty slice", resp.Duts)
		}
	})
	t.Run("duts added", func(t *testing.T) {
		t.Parallel()

		// Set up fake datastore.
		ctx := gaetesting.TestingContextWithAppID("some-app")
		expireTime := time.Date(2001, 2, 3, 4, 5, 6, 7, time.UTC)
		freeduts.Add(ctx, []freeduts.DUT{
			{
				ID:         "c7b2ae28-d597-4316-be5f-7df23c762c1e",
				Hostname:   "firo.example.com",
				Bug:        "crbug.com/1234",
				Comment:    "removed for testing",
				ExpireTime: expireTime,
				Model:      "firorial",
			},
		})
		datastore.Raw(ctx).GetTestable().CatchupIndexes()

		// Test RPC.
		var is ServerImpl
		resp, err := is.ListRemovedDuts(ctx, &fleet.ListRemovedDutsRequest{})
		if err != nil {
			t.Fatalf("ListRemovedDuts returned error: %s", err)
		}
		want := fleet.ListRemovedDutsResponse{
			Duts: []*fleet.ListRemovedDutsResponse_Dut{
				{
					Id:       "c7b2ae28-d597-4316-be5f-7df23c762c1e",
					Hostname: "firo.example.com",
					Bug:      "crbug.com/1234",
					Comment:  "removed for testing",
					ExpireTime: &timestamp.Timestamp{
						Seconds: expireTime.Unix(),
						// datastore only has second resolution.
						Nanos: 0,
					},
					Model: "firorial",
				},
			},
		}
		if diff := pretty.Compare(want, resp); diff != "" {
			t.Errorf("Unexpected response -want +got, %s", diff)
		}
	})
}

func TestGetDutInfoWithConsistentDatastore(t *testing.T) {
	Convey("On happy path and a single DUT in the inventory", t, func() {
		ctx := testingContext()
		ctx = withDutInfoCacheValidity(ctx, 100*time.Minute)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
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
		})
	})
}

func TestGetDutInfoWithEventuallyConsistentDatastore(t *testing.T) {
	Convey("With eventually consistent datastore and a single DUT in the inventory", t, func() {
		ctx := testingContext()
		ctx = withDutInfoCacheValidity(ctx, 100*time.Second)
		datastore.GetTestable(ctx).Consistent(false)
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()

		setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
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
					setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
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

func withDutInfoCacheValidity(ctx context.Context, v time.Duration) context.Context {
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

func getDutInfoBasic(t *testing.T, di *fleet.GetDutInfoResponse) *inventory.DeviceUnderTest {
	t.Helper()
	var dut inventory.DeviceUnderTest
	if di.Spec == nil {
		t.Fatalf("Got nil spec")
	}
	err := proto.Unmarshal(di.Spec, &dut)
	if err != nil {
		t.Fatalf("Unmarshal DutInfo returned non-nil error: %s", err)
	}
	return &dut
}

// Maximum time to failure: (2^7 - 1)*(50/1000) = 6.35 seconds
var testRetriesTemplate = retry.ExponentialBackoff{
	Limited: retry.Limited{
		Delay:   50 * time.Millisecond,
		Retries: 7,
	},
	MaxDelay:   5 * time.Second,
	Multiplier: 2,
}

func testRetryIteratorFactory() retry.Iterator {
	it := testRetriesTemplate
	return &it
}
