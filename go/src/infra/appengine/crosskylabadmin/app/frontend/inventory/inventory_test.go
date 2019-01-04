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
	"strings"
	"testing"

	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{})
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_healthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link", "DUT_POOL_SUITES"},
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link", "DUT_POOL_SUITES"},
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link", "DUT_POOL_SUITES"},
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unknown", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link", "DUT_POOL_SUITES"},
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
		So(tf.FakeGitiles.addArchive(config.Get(tf.C).Inventory, []byte(ptext), nil), ShouldBeNil)
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy_1", "link", "DUT_POOL_CQ"},
			{"link_cq_unhealthy_2", "link", "DUT_POOL_CQ"},
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

type testDutOnServer struct {
	id     string
	server string
}

func TestEnsurePoolHealthyCommit(t *testing.T) {
	Convey("EnsurePoolHealthy commits expected changes to gerrit", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_cq_unhealthy", "link", "DUT_POOL_CQ"},
			{"link_suites_healthy", "link", "DUT_POOL_SUITES"},
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
			{"link_cq_unhealthy", "link", "DUT_POOL_SUITES"},
			{"link_suites_healthy", "link", "DUT_POOL_CQ"},
		})
	})
}

func TestResizePool(t *testing.T) {
	Convey("With 0 DUTs in target pool and 0 DUTs in spare pool", t, func(c C) {
		tf, validate := newTestFixture(t)
		defer validate()

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{})
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link", "DUT_POOL_SUITES"},
			{"link_suites_1", "link", "DUT_POOL_SUITES"},
			{"link_suites_2", "link", "DUT_POOL_SUITES"},
			{"link_suites_3", "link", "DUT_POOL_SUITES"},
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link", "DUT_POOL_CQ"},
			{"link_suites_1", "link", "DUT_POOL_CQ"},
			{"link_suites_2", "link", "DUT_POOL_CQ"},
			{"link_suites_3", "link", "DUT_POOL_CQ"},
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

		err := setupLabInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryDut{
			{"link_suites_0", "link", "DUT_POOL_SUITES"},
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
				{"link_suites_0", "link", "DUT_POOL_CQ"},
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

func TestRemoveDutsFromDrones(t *testing.T) {
	Convey("With 1 DUT assigned to a drone", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		dutID := "dut_id"
		serverID := "server_id"
		err := setupInfraInventoryArchive(tf.C, tf.FakeGitiles, []testDutOnServer{
			{dutID, serverID},
		})
		So(err, ShouldBeNil)

		Convey("DeactivateDut for that dut removes it from drone.", func() {
			req := &fleet.RemoveDutsFromDronesRequest{
				Removals: []*fleet.RemoveDutsFromDronesRequest_Item{{DutId: dutID}},
			}
			resp, err := tf.Inventory.RemoveDutsFromDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp.Removed, ShouldHaveLength, 1)
			So(resp.Removed[0].DutId, ShouldEqual, dutID)

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[0]
			So(change.Path, ShouldEqual, "data/skylab/server_db.textpb")

			contents := change.Content
			infra := &inventory.Infrastructure{}
			err = inventory.LoadInfrastructureFromString(contents, infra)
			So(err, ShouldBeNil)
			So(infra.Servers, ShouldHaveLength, 1)
			So(infra.Servers[0].DutUids, ShouldBeEmpty)
		})

		Convey("DeactivateDut for a nonexistant dut returns no results.", func() {
			req := &fleet.RemoveDutsFromDronesRequest{
				Removals: []*fleet.RemoveDutsFromDronesRequest_Item{{DutId: "foo"}},
			}
			resp, err := tf.Inventory.RemoveDutsFromDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp.Removed, ShouldBeEmpty)
			So(resp.Url, ShouldEqual, "")
		})
	})
}

func setupInfraInventoryArchive(c context.Context, g *fakeGitilesClient, duts []testDutOnServer) error {
	return g.addArchive(config.Get(c).Inventory, nil, []byte(infraInventoryStrFromDuts(duts)))
}

// assertLabInventoryChange verifies that the CL uploaded to gerrit contains the
// inventory of duts provided.
func assertLabInventoryChange(c C, fg *fakeGerritClient, duts []testInventoryDut) {
	changes := fg.Changes
	So(changes, ShouldHaveLength, 1)
	change := changes[0]
	So(change.Path, ShouldEqual, "data/skylab/lab.textpb")
	var actualLab inventory.Lab
	err := inventory.LoadLabFromString(change.Content, &actualLab)
	So(err, ShouldBeNil)
	var expectedLab inventory.Lab
	err = inventory.LoadLabFromString(labInventoryStrFromDuts(duts), &expectedLab)
	So(err, ShouldBeNil)
	if !proto.Equal(&actualLab, &expectedLab) {
		prettyPrintLabDiff(c, &expectedLab, &actualLab)
		So(proto.Equal(&actualLab, &expectedLab), ShouldBeTrue)
	}
}

// TODO(akeshet): Consider eliminating this helper and marshalling directly to a byte buffer
// in addArchive.
func infraInventoryStrFromDuts(duts []testDutOnServer) string {
	infra := &inventory.Infrastructure{}
	serversByName := make(map[string]*inventory.Server)
	for _, d := range duts {
		server, ok := serversByName[d.server]
		if !ok {
			server = dutTestServer(d.server)
			serversByName[d.server] = server
		}
		server.DutUids = append(server.DutUids, d.id)
	}
	infra.Servers = make([]*inventory.Server, 0, len(serversByName))
	for _, s := range serversByName {
		infra.Servers = append(infra.Servers, s)
	}

	return proto.MarshalTextString(infra)
}

func dutTestServer(serverName string) *inventory.Server {
	env := inventory.Environment_ENVIRONMENT_STAGING
	status := inventory.Server_STATUS_PRIMARY
	return &inventory.Server{
		Hostname:    &serverName,
		Environment: &env,
		Status:      &status,
	}
}

func expectDutsWithHealth(t *fleet.MockTrackerServer, dutHealths map[string]fleet.Health) {
	ft := &trackerPartialFake{dutHealths}
	t.EXPECT().SummarizeBots(gomock.Any(), gomock.Any()).AnyTimes().DoAndReturn(ft.SummarizeBots)
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

func prettyPrintLabDiff(c C, want, got *inventory.Lab) {
	w, _ := inventory.WriteLabToString(want)
	g, _ := inventory.WriteLabToString(got)
	c.Printf("submitted incorrect lab -want +got: %s", pretty.Compare(strings.Split(w, "\n"), strings.Split(g, "\n")))
}
