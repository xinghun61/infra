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

package inventory

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/libs/skylab/inventory"
	"testing"

	"github.com/golang/mock/gomock"
	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/errors"
)

func TestDeleteDuts(t *testing.T) {
	Convey("With 3 DUTs in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname_1", "link", "DUT_POOL_SUITES"},
				{"dut_id_2", "dut_hostname_2", "link", "DUT_POOL_SUITES"},
				{"dut_id_3", "dut_hostname_3", "link", "DUT_POOL_SUITES"},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeleteDuts with no hostnames returns error", func() {
			_, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeleteDuts with unknown hostname deletes no duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"unknown_hostname"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.GetIds(), ShouldBeEmpty)
		})

		Convey("DeleteDuts with known hostnames deletes duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"dut_hostname_1", "dut_hostname_2"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(stringset.NewFromSlice(resp.GetIds()...), ShouldResemble, stringset.NewFromSlice("dut_id_1", "dut_id_2"))
		})
	})

	Convey("With 2 DUTs with the same hostname", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname", "link", "DUT_POOL_SUITES"},
				{"dut_id_2", "dut_hostname", "link", "DUT_POOL_SUITES"},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeleteDuts with known hostname deletes both duts", func() {
			resp, err := tf.Inventory.DeleteDuts(tf.C, &fleet.DeleteDutsRequest{Hostnames: []string{"dut_hostname"}})
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(stringset.NewFromSlice(resp.GetIds()...), ShouldResemble, stringset.NewFromSlice("dut_id_1", "dut_id_2"))
		})
	})
}

func TestDeployDut(t *testing.T) {
	Convey("With no DUTs and one drone in the inventory", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		err := tf.FakeGitiles.SetInventory(config.Get(tf.C).Inventory, fakes.InventoryData{
			Infrastructure: inventoryBytesFromServers([]testInventoryServer{
				{
					hostname:    "fake-drone.google.com",
					environment: inventory.Environment_ENVIRONMENT_STAGING,
				},
			}),
		})
		So(err, ShouldBeNil)

		Convey("DeployDut with empty new_spec returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut with invlalid new_specs returns error", func() {
			_, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: []byte("clearly not a protobuf"),
			})
			So(err, ShouldNotBeNil)
		})

		Convey("DeployDut with valid new_specs triggers deploy", func() {
			// Id is a required field, so must be set.
			// But a new ID is assigned on deployment.
			ignoredID := "This ID is ignored"
			dutHostname := "fake-dut"
			specs := &inventory.CommonDeviceSpecs{
				Id:       &ignoredID,
				Hostname: &dutHostname,
			}
			ns, err := proto.Marshal(specs)
			So(err, ShouldBeNil)

			// TODO(pprabhu) Check arguments of this call after testing utilities
			// from ../test_common.go are refactored into a package.
			deployTaskID := "swarming-task"
			tf.MockSwarming.EXPECT().CreateTask(gomock.Any(), gomock.Any(), gomock.Any()).Return(deployTaskID, nil)
			resp, err := tf.Inventory.DeployDut(tf.C, &fleet.DeployDutRequest{
				NewSpecs: ns,
			})
			So(err, ShouldBeNil)
			deploymentID := resp.DeploymentId
			So(deploymentID, ShouldNotEqual, "")

			lab, err := getLabFromChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(lab.Duts, ShouldHaveLength, 1)
			dut := lab.Duts[0]
			common := dut.GetCommon()
			So(common.GetId(), ShouldNotEqual, "")
			So(common.GetId(), ShouldNotEqual, specs.GetId())
			So(common.GetHostname(), ShouldEqual, specs.GetHostname())

			infra, err := getInfrastructureFromChange(tf.FakeGerrit)
			So(err, ShouldBeNil)
			So(infra.Servers, ShouldHaveLength, 1)
			server := infra.Servers[0]
			So(server.GetHostname(), ShouldEqual, "fake-drone.google.com")
			So(server.DutUids, ShouldHaveLength, 1)
			So(server.DutUids[0], ShouldEqual, common.GetId())

			Convey("then GetDeploymentStatus with wrong ID returns error", func() {
				_, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: "incorrct-id"})
				So(err, ShouldNotBeNil)
			})

			Convey("then GetDeploymentStatus with correct ID returns IN_PROGRESS status", func() {
				tf.MockSwarming.EXPECT().GetTaskResult(gomock.Any(), deployTaskID).Return(&swarming.SwarmingRpcsTaskResult{
					State: "RUNNING",
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS)
				So(resp.ChangeUrl, ShouldNotEqual, "")
				So(resp.TaskUrl, ShouldContainSubstring, deployTaskID)
			})

			Convey("then GetDeploymentStatus with correct ID returns COMPLETED status on task success", func() {
				tf.MockSwarming.EXPECT().GetTaskResult(gomock.Any(), deployTaskID).Return(&swarming.SwarmingRpcsTaskResult{
					State: "COMPLETED",
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED)
			})

			Convey("then GetDeploymentStatus with correct ID returns FAILURE status on task failure", func() {
				tf.MockSwarming.EXPECT().GetTaskResult(gomock.Any(), deployTaskID).Return(&swarming.SwarmingRpcsTaskResult{
					State:   "COMPLETED",
					Failure: true,
				}, nil)
				resp, err := tf.Inventory.GetDeploymentStatus(tf.C, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
				So(err, ShouldBeNil)
				So(resp.Status, ShouldEqual, fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_FAILED)
			})
		})
	})
}

// getLabFromChange gets the inventory.Lab committed to fakes.GerritClient
//
// This function assumes that only one change was committed.
func getLabFromChange(fg *fakes.GerritClient) (*inventory.Lab, error) {
	if len(fg.Changes) != 1 {
		return nil, errors.Reason("want 1 gerrit change, found %d", len(fg.Changes)).Err()
	}

	change := fg.Changes[0]
	f, ok := change.Files["data/skylab/lab.textpb"]
	if !ok {
		return nil, errors.Reason("No modification to Lab in gerrit change").Err()
	}
	var lab inventory.Lab
	err := inventory.LoadLabFromString(f, &lab)
	return &lab, err
}

// getInfrastructureFromChange gets the inventory.Infrastructure committed to
// fakes.GerritClient
//
// This function assumes that only one change was committed.
func getInfrastructureFromChange(fg *fakes.GerritClient) (*inventory.Infrastructure, error) {
	if len(fg.Changes) != 1 {
		return nil, errors.Reason("want 1 gerrit change, found %d", len(fg.Changes)).Err()
	}

	change := fg.Changes[0]
	f, ok := change.Files["data/skylab/server_db.textpb"]
	if !ok {
		return nil, errors.Reason("No modification to Infrastructure in gerrit change").Err()
	}
	var infra inventory.Infrastructure
	err := inventory.LoadInfrastructureFromString(f, &infra)
	return &infra, err
}
