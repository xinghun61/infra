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
	"fmt"
	"strings"
	"testing"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/appengine/crosskylabadmin/app/frontend/test"
	"infra/libs/skylab/inventory"

	"github.com/golang/mock/gomock"
	"github.com/kylelemons/godebug/pretty"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	. "github.com/smartystreets/goconvey/convey"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestBalancePoolsDryrun(t *testing.T) {
	Convey("BalancePools (dryrun) with empty DutSelector", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
			{"coral_cq_unhealthy", "coral_cq_unhealthy", "coral", "DUT_POOL_CQ"},
			{"coral_suites_healthy", "coral_suites_healthy", "coral", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unhealthy", "repair_failed", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
			test.BotForDUT("coral_cq_unhealthy", "repair_failed", "label-model:coral"),
			test.BotForDUT("coral_suites_healthy", "ready", "label-model:coral"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(len(resp.ModelResult), ShouldEqual, 2)
		fmt.Println(resp.ModelResult)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		r2, ok := resp.ModelResult["coral"]
		So(ok, ShouldBeTrue)
		So(r.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(r2.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r2.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(r2.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		changes := collectChanges(resp.ModelResult)
		mc := poolChangeMap(changes)
		So(mc, ShouldResemble, map[string]*partialPoolChange{
			"link_cq_unhealthy": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"link_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
			"coral_cq_unhealthy": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"coral_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
		})
		So(r.Failures, ShouldHaveLength, 0)
	})
	Convey("BalancePools (dryrun) succeeds with no changes for empty inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{})
		So(err, ShouldBeNil)
		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "suites",
			TargetPool: "cq",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})
		So(err, ShouldBeNil)
		So(resp.ModelResult, ShouldBeNil)
	})

	Convey("BalancePools (dryrun) swaps no DUT with all DUTs healthy", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_healthy", "link_cq_healthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_healthy", "ready", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})
		So(err, ShouldBeNil)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		fmt.Println(r)
		So(r.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(r.Changes, ShouldHaveLength, 0)
		So(r.Failures, ShouldHaveLength, 0)
	})
	Convey("BalancePools (dryrun) swaps one DUT with one DUT needed and one available", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unhealthy", "repair_failed", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(len(resp.ModelResult), ShouldEqual, 1)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		So(r.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		changes := collectChanges(resp.ModelResult)
		mc := poolChangeMap(changes)
		So(mc, ShouldResemble, map[string]*partialPoolChange{
			"link_cq_unhealthy": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"link_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
		})
		So(r.Failures, ShouldHaveLength, 0)
	})

	Convey("BalancePools (dryrun) swaps one DUT and reports failure with two DUTs needed but one available", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unhealthy_1", "repair_failed", "label-model:link"),
			test.BotForDUT("link_cq_unhealthy_2", "repair_failed", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		So(r.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 2)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		changes := collectChanges(resp.ModelResult)
		mc := poolChangeMap(changes)
		So(mc["link_suites_healthy"], ShouldResemble, &partialPoolChange{
			OldPool: "DUT_POOL_SUITES",
			NewPool: "DUT_POOL_CQ",
		})
		if d, ok := mc["link_cq_unhealthy_1"]; ok {
			So(d, ShouldResemble, &partialPoolChange{
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			})
		} else if d, ok := mc["link_cq_unhealthy_2"]; ok {
			So(d, ShouldResemble, &partialPoolChange{
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			})
		} else {
			t.Error("no DUT swapped out of target pool")
		}

		So(collectFailures(resp.ModelResult), ShouldResemble, []fleet.EnsurePoolHealthyResponse_Failure{fleet.EnsurePoolHealthyResponse_NOT_ENOUGH_HEALTHY_SPARES})
	})

	Convey("BalancePools (dryrun) treats target DUT with unknown health as unhealthy", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unknown", "link_cq_unknown", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unknown", "unknown", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		So(r.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		changes := collectChanges(resp.ModelResult)
		mc := poolChangeMap(changes)
		So(mc, ShouldResemble, map[string]*partialPoolChange{
			"link_cq_unknown": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"link_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
		})

		So(collectFailures(resp.ModelResult), ShouldHaveLength, 0)
	})

	Convey("BalancePools (dryrun) swaps no DUTs and reports failure with too many unhealthy DUTs", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
		})
		So(err, ShouldBeNil)

		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unhealthy_1", "repair_failed", "label-model:link"),
			test.BotForDUT("link_cq_unhealthy_2", "repair_failed", "label-model:link"),
		})

		resp, err := tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:        "DUT_POOL_SUITES",
			TargetPool:       "DUT_POOL_CQ",
			MaxUnhealthyDuts: 1,
			Options:          &fleet.BalancePoolsRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		r, ok := resp.ModelResult["link"]
		So(ok, ShouldBeTrue)
		So(r.GetTargetPoolStatus().GetSize(), ShouldEqual, 2)
		So(r.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(r.Changes, ShouldHaveLength, 0)
		So(r.Failures, ShouldResemble, []fleet.EnsurePoolHealthyResponse_Failure{fleet.EnsurePoolHealthyResponse_TOO_MANY_UNHEALTHY_DUTS})
	})
}

func TestBalancePoolsCommit(t *testing.T) {
	Convey("BalancePools commits expected changes to gerrit", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
			{"coral_cq_unhealthy", "coral_cq_unhealthy", "coral", "DUT_POOL_CQ"},
			{"coral_suites_healthy", "coral_suites_healthy", "coral", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		expectDutsHealthFromSwarming(tf, []*swarming.SwarmingRpcsBotInfo{
			test.BotForDUT("link_cq_unhealthy", "repair_failed", "label-model:link"),
			test.BotForDUT("link_suites_healthy", "ready", "label-model:link"),
			test.BotForDUT("coral_cq_unhealthy", "repair_failed", "label-model:coral"),
			test.BotForDUT("coral_suites_healthy", "ready", "label-model:coral"),
		})

		_, err = tf.Inventory.BalancePools(tf.C, &fleet.BalancePoolsRequest{
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
		})
		So(err, ShouldBeNil)

		assertLabInventoryChange(c, tf.FakeGerrit, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_SUITES"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_CQ"},
			{"coral_cq_unhealthy", "coral_cq_unhealthy", "coral", "DUT_POOL_SUITES"},
			{"coral_suites_healthy", "coral_suites_healthy", "coral", "DUT_POOL_CQ"},
		})
	})
}

func TestEnsurePoolHealthyDryrun(t *testing.T) {
	Convey("EnsurePoolHealthy(dryrun) fails with no DutSelector", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		_, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			Options: &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})
		So(err, ShouldErrLike, status.Errorf(codes.InvalidArgument, ""))
	})

	Convey("EnsurePoolHealthy succeeds with no changes for empty inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{})
		So(err, ShouldBeNil)

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "suites",
			TargetPool: "cq",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})
		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 0)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.Changes, ShouldHaveLength, 0)
		So(resp.Failures, ShouldHaveLength, 0)
	})

	Convey("EnsurePoolHealthy swaps no DUT with all DUTs healthy", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_healthy", "link_cq_healthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_cq_healthy":     fleet.Health_Healthy,
			"link_suites_healthy": fleet.Health_Healthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})
		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(resp.Changes, ShouldHaveLength, 0)
		So(resp.Failures, ShouldHaveLength, 0)
	})

	Convey("EnsurePoolHealthy swaps one DUT with one DUT needed and one available", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_cq_unhealthy":   fleet.Health_Unhealthy,
			"link_suites_healthy": fleet.Health_Healthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		mc := poolChangeMap(resp.Changes)
		So(mc, ShouldResemble, map[string]*partialPoolChange{
			"link_cq_unhealthy": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"link_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
		})

		So(resp.Failures, ShouldHaveLength, 0)
	})

	Convey("EnsurePoolHealthy swaps one DUT and reports failure with two DUTs needed but one available", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_cq_unhealthy_1": fleet.Health_Unhealthy,
			"link_cq_unhealthy_2": fleet.Health_Unhealthy,
			"link_suites_healthy": fleet.Health_Healthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 2)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		So(resp.Changes, ShouldHaveLength, 2)
		mc := poolChangeMap(resp.Changes)
		So(mc["link_suites_healthy"], ShouldResemble, &partialPoolChange{
			OldPool: "DUT_POOL_SUITES",
			NewPool: "DUT_POOL_CQ",
		})
		if d, ok := mc["link_cq_unhealthy_1"]; ok {
			So(d, ShouldResemble, &partialPoolChange{
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			})
		} else if d, ok := mc["link_cq_unhealthy_2"]; ok {
			So(d, ShouldResemble, &partialPoolChange{
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			})
		} else {
			t.Error("no DUT swapped out of target pool")
		}

		So(resp.Failures, ShouldResemble, []fleet.EnsurePoolHealthyResponse_Failure{fleet.EnsurePoolHealthyResponse_NOT_ENOUGH_HEALTHY_SPARES})
	})

	Convey("EnsurePoolHealthy treats target DUT with unknown health as unhealthy", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unknown", "link_cq_unknown", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_suites_healthy": fleet.Health_Healthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)

		mc := poolChangeMap(resp.Changes)
		So(mc, ShouldResemble, map[string]*partialPoolChange{
			"link_cq_unknown": {
				OldPool: "DUT_POOL_CQ",
				NewPool: "DUT_POOL_SUITES",
			},
			"link_suites_healthy": {
				OldPool: "DUT_POOL_SUITES",
				NewPool: "DUT_POOL_CQ",
			},
		})

		So(resp.Failures, ShouldHaveLength, 0)
	})

	Convey("EnsurePoolHealthy filters DUTs by environment", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		ptext := `
			duts {
				common {
					id: "dut_in_env"
					hostname: "dut_in_env"
					labels {
						model: "link"
						critical_pools: DUT_POOL_CQ
					}
					environment: ENVIRONMENT_STAGING
				}
			}
			duts {
				common {
					id: "dut_not_in_env"
					hostname: "dut_not_in_env"
					labels {
						model: "link"
						critical_pools: DUT_POOL_CQ
					}
					environment: ENVIRONMENT_PROD
				}
			}
		`
		So(
			tf.FakeGitiles.SetInventory(
				config.Get(tf.C).Inventory,
				fakes.InventoryData{Lab: []byte(ptext)},
			),
			ShouldBeNil,
		)
		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"dut_in_env":    fleet.Health_Healthy,
			"dut_no_in_env": fleet.Health_Healthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
			Options:    &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})
		So(err, ShouldBeNil)
		So(resp.GetSparePoolStatus().GetSize(), ShouldEqual, 0)
		So(resp.GetSparePoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 1)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 1)
		So(resp.Changes, ShouldHaveLength, 0)
		So(resp.Failures, ShouldHaveLength, 0)
	})

	Convey("EnsurePoolHealthy swaps no DUTs and reports failure with too many unhealthy DUTs", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
		})
		So(err, ShouldBeNil)

		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_cq_unhealthy_1": fleet.Health_Unhealthy,
			"link_cq_unhealthy_2": fleet.Health_Unhealthy,
		})

		resp, err := tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:        "DUT_POOL_SUITES",
			TargetPool:       "DUT_POOL_CQ",
			MaxUnhealthyDuts: 1,
			Options:          &fleet.EnsurePoolHealthyRequest_Options{Dryrun: true},
		})

		So(err, ShouldBeNil)
		So(resp.GetTargetPoolStatus().GetSize(), ShouldEqual, 2)
		So(resp.GetTargetPoolStatus().GetHealthyCount(), ShouldEqual, 0)
		So(resp.Changes, ShouldHaveLength, 0)
		So(resp.Failures, ShouldResemble, []fleet.EnsurePoolHealthyResponse_Failure{fleet.EnsurePoolHealthyResponse_TOO_MANY_UNHEALTHY_DUTS})
	})
}

func TestEnsurePoolHealthyCommit(t *testing.T) {
	Convey("EnsurePoolHealthy commits expected changes to gerrit", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)
		expectDutsWithHealth(tf.MockTracker, map[string]fleet.Health{
			"link_cq_unhealthy":   fleet.Health_Unhealthy,
			"link_suites_healthy": fleet.Health_Healthy,
		})

		_, err = tf.Inventory.EnsurePoolHealthy(tf.C, &fleet.EnsurePoolHealthyRequest{
			DutSelector: &fleet.DutSelector{
				Model: "link",
			},
			SparePool:  "DUT_POOL_SUITES",
			TargetPool: "DUT_POOL_CQ",
		})
		So(err, ShouldBeNil)

		assertLabInventoryChange(c, tf.FakeGerrit, []testInventoryDut{
			{"link_cq_unhealthy", "link_cq_unhealthy", "link", "DUT_POOL_SUITES"},
			{"link_suites_healthy", "link_suites_healthy", "link", "DUT_POOL_CQ"},
		})
	})
}

func TestResizePool(t *testing.T) {
	Convey("With 0 DUTs in target pool and 0 DUTs in spare pool", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{})
		So(err, ShouldBeNil)

		Convey("ResizePool to 0 DUTs in target pool makes no changes", func() {
			resp, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 0,
			})
			So(err, ShouldBeNil)
			So(resp.Url, ShouldEqual, "")
			So(resp.Changes, ShouldHaveLength, 0)
		})

		Convey("ResizePool to 1 DUTs in target pool fails", func() {
			_, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 1,
			})
			So(err, ShouldNotBeNil)
		})
	})

	Convey("With 0 DUTs in target pool and 4 DUTs in spare pool", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link_suites_0", "link", "DUT_POOL_SUITES"},
			{"link_suites_1", "link_suites_1", "link", "DUT_POOL_SUITES"},
			{"link_suites_2", "link_suites_2", "link", "DUT_POOL_SUITES"},
			{"link_suites_3", "link_suites_3", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		Convey("ResizePool to 0 DUTs in target pool makes no changes", func() {
			resp, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 0,
			})
			So(err, ShouldBeNil)
			So(resp.Url, ShouldEqual, "")
			So(resp.Changes, ShouldHaveLength, 0)
		})

		Convey("ResizePool to 3 DUTs in target pool expands target pool", func() {
			resp, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 3,
			})
			So(err, ShouldBeNil)
			So(resp.Url, ShouldNotEqual, "")
			So(resp.Changes, ShouldHaveLength, 3)
			mc := poolChangeMap(resp.Changes)
			So(poolChangeCount(mc, "DUT_POOL_SUITES", "DUT_POOL_CQ"), ShouldEqual, 3)
		})

		Convey("ResizePool to 5 DUTs in target pool fails", func() {
			_, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 5,
			})
			So(err, ShouldNotBeNil)
		})
	})

	Convey("With 4 DUTs in target pool and 0 DUTs in spare pool", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link_suites_0", "link", "DUT_POOL_CQ"},
			{"link_suites_1", "link_suites_1", "link", "DUT_POOL_CQ"},
			{"link_suites_2", "link_suites_2", "link", "DUT_POOL_CQ"},
			{"link_suites_3", "link_suites_3", "link", "DUT_POOL_CQ"},
		})
		So(err, ShouldBeNil)

		Convey("ResizePool to 4 DUTs in target pool makes no changes", func() {
			resp, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 4,
			})
			So(err, ShouldBeNil)
			So(resp.Url, ShouldEqual, "")
			So(resp.Changes, ShouldHaveLength, 0)
		})

		Convey("ResizePool to 3 DUTs in target pool contracts target pool", func() {
			resp, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 3,
			})
			So(err, ShouldBeNil)
			So(resp.Url, ShouldNotEqual, "")
			So(resp.Changes, ShouldHaveLength, 1)
			mc := poolChangeMap(resp.Changes)
			So(poolChangeCount(mc, "DUT_POOL_CQ", "DUT_POOL_SUITES"), ShouldEqual, 1)
		})
	})
}

func TestResizePoolCommit(t *testing.T) {
	Convey("With 0 DUTs in target pool and 1 DUTs in spare pool", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setGitilesDUTs(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link_suites_0", "link", "DUT_POOL_SUITES"},
		})
		So(err, ShouldBeNil)

		Convey("ResizePool to 1 DUTs in target pool commits changes", func() {
			_, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 1,
			})
			So(err, ShouldBeNil)
			assertLabInventoryChange(c, tf.FakeGerrit, []testInventoryDut{
				{"link_suites_0", "link_suites_0", "link", "DUT_POOL_CQ"},
			})
		})

		Convey("ResizePool does not commit changes on error", func() {
			_, err := tf.Inventory.ResizePool(tf.C, &fleet.ResizePoolRequest{
				DutSelector: &fleet.DutSelector{
					Model: "link",
				},
				SparePool:      "DUT_POOL_SUITES",
				TargetPool:     "DUT_POOL_CQ",
				TargetPoolSize: 4,
			})
			So(err, ShouldNotBeNil)
			So(tf.FakeGerrit.Changes, ShouldHaveLength, 0)
		})
	})
}

// partialPoolChange contains a subset of the fleet.PoolChange fields.
//
// This struct is used for easy validation of relevant fields of
// fleet.PoolChange values returned from API responses.
type partialPoolChange struct {
	NewPool string
	OldPool string
}

// poolChangeMap converts a list of fleet.PoolChanges to a map from DutId to
// partialPoolChange.
//
// The returned map is more convenient for comparison with ShouldResemble
// assertions than the original list.
func poolChangeMap(pcs []*fleet.PoolChange) map[string]*partialPoolChange {
	mc := make(map[string]*partialPoolChange)
	for _, c := range pcs {
		mc[c.DutId] = &partialPoolChange{
			NewPool: c.NewPool,
			OldPool: c.OldPool,
		}
	}
	return mc
}

// poolChangeCount counts the number of partialPoolChanges in the map that move
// a DUT from oldPool to newPool.
func poolChangeCount(pcs map[string]*partialPoolChange, oldPool, newPool string) int {
	c := 0
	for _, pc := range pcs {
		if pc.OldPool == oldPool && pc.NewPool == newPool {
			c++
		}
	}
	return c
}

// assertLabInventoryChange verifies that the CL uploaded to gerrit contains the
// inventory of duts provided.
func assertLabInventoryChange(c C, fg *fakes.GerritClient, duts []testInventoryDut) {
	p := "data/skylab/lab.textpb"
	changes := fg.Changes
	So(changes, ShouldHaveLength, 1)
	change := changes[0]
	So(change.Files, ShouldContainKey, p)
	var actualLab inventory.Lab
	err := inventory.LoadLabFromString(change.Files[p], &actualLab)
	So(err, ShouldBeNil)
	var expectedLab inventory.Lab
	err = inventory.LoadLabFromString(string(inventoryBytesFromDUTs(duts)), &expectedLab)
	So(err, ShouldBeNil)
	// Sort before comparison
	want, _ := inventory.WriteLabToString(&expectedLab)
	got, _ := inventory.WriteLabToString(&actualLab)
	c.Printf("submitted incorrect lab -want +got: %s", pretty.Compare(strings.Split(want, "\n"), strings.Split(got, "\n")))
	So(want, ShouldEqual, got)
}

func expectDutsWithHealth(t *fleet.MockTrackerServer, dutHealths map[string]fleet.Health) {
	ft := &trackerPartialFake{dutHealths}
	t.EXPECT().SummarizeBots(gomock.Any(), gomock.Any()).AnyTimes().DoAndReturn(ft.SummarizeBots)
}

func expectDutsHealthFromSwarming(tf testFixture, bots []*swarming.SwarmingRpcsBotInfo) {
	tf.MockSwarming.EXPECT().ListAliveBotsInPool(
		gomock.Any(), gomock.Eq(config.Get(tf.C).Swarming.BotPool), gomock.Any(),
	).AnyTimes().DoAndReturn(test.FakeListAliveBotsInPool(bots))
}

func collectFailures(mrs map[string]*fleet.EnsurePoolHealthyResponse) []fleet.EnsurePoolHealthyResponse_Failure {
	ret := make([]fleet.EnsurePoolHealthyResponse_Failure, 0)
	for _, res := range mrs {
		ret = append(ret, res.Failures...)
	}
	return ret
}
