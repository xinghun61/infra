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

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRemoveDutsFromDrones(t *testing.T) {
	Convey("With 2 DUTs assigned to drones (1 in prod, 1 in staging)", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		dutID := "dut_id"
		serverID := "server_id"
		wrongEnvDutID := "wrong_env_dut"
		wrongEnvServer := "wrong_env_server"
		err := setupInfraInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryServer{
			{
				hostname:    serverID,
				environment: inventory.Environment_ENVIRONMENT_STAGING,
				dutIDs:      []string{dutID},
			},
			{
				hostname:    wrongEnvServer,
				environment: inventory.Environment_ENVIRONMENT_PROD,
				dutIDs:      []string{wrongEnvDutID},
			},
		})
		So(err, ShouldBeNil)

		Convey("DeactivateDut for the staging dut removes it from drone.", func() {
			req := &fleet.RemoveDutsFromDronesRequest{
				Removals: []*fleet.RemoveDutsFromDronesRequest_Item{{DutId: dutID}},
			}
			resp, err := tf.Inventory.RemoveDutsFromDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp.Removed, ShouldHaveLength, 1)
			So(resp.Removed[0].DutId, ShouldEqual, dutID)

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[0]
			p := "data/skylab/server_db.textpb"
			So(change.Files, ShouldContainKey, p)

			contents := change.Files[p]
			infra := &inventory.Infrastructure{}
			err = inventory.LoadInfrastructureFromString(contents, infra)
			So(err, ShouldBeNil)
			So(change.Subject, ShouldStartWith, "remove DUTs")
			So(infra.Servers, ShouldHaveLength, 2)

			var server *inventory.Server
			for _, s := range infra.Servers {
				if s.GetHostname() == serverID {
					server = s
					break
				}
			}
			So(server.DutUids, ShouldBeEmpty)
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

		Convey("DeactivateDut for prod dut returns no results.", func() {
			req := &fleet.RemoveDutsFromDronesRequest{
				Removals: []*fleet.RemoveDutsFromDronesRequest_Item{{DutId: wrongEnvDutID}},
			}
			resp, err := tf.Inventory.RemoveDutsFromDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp.Removed, ShouldBeEmpty)
			So(resp.Url, ShouldEqual, "")
		})
	})
}

func TestAssignDutsToDrones(t *testing.T) {
	Convey("With 2 DUT assigned to drones (1 in prod, 1 in staging)", t, func() {
		tf, validate := newTestFixture(t)
		defer validate()

		existingDutID := "dut_id_1"
		serverID := "server_id"
		wrongEnvDutID := "wrong_env_dut"
		wrongEnvServer := "wrong_env_server"
		err := setupInfraInventoryArchive(tf.C, tf.FakeGitiles, []testInventoryServer{
			{
				hostname:    serverID,
				environment: inventory.Environment_ENVIRONMENT_STAGING,
				dutIDs:      []string{existingDutID},
			},
			{
				hostname:    wrongEnvServer,
				environment: inventory.Environment_ENVIRONMENT_PROD,
				dutIDs:      []string{wrongEnvDutID},
			},
		})
		So(err, ShouldBeNil)

		Convey("AssignDutsToDrones with an already assigned dut in current environment should return an appropriate error.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: existingDutID, DroneHostname: serverID},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "already assigned")
			So(err.Error(), ShouldContainSubstring, inventory.Environment_ENVIRONMENT_STAGING.String())
		})

		Convey("AssignDutsToDrones with an already assigned dut in other environment should return an appropriate error.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: wrongEnvDutID, DroneHostname: serverID},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "already assigned")
			So(err.Error(), ShouldContainSubstring, inventory.Environment_ENVIRONMENT_PROD.String())
		})

		newDutID := "dut_id_2"

		Convey("AssignDutsToDrones with a nonexistant drone should return an appropriate error.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: newDutID, DroneHostname: "foo_host"},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(resp, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(err.Error(), ShouldContainSubstring, "does not exist")
		})

		Convey("AssignDutsToDrones with a new dut and existing drone assigns that dut.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: newDutID, DroneHostname: serverID},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.Assigned, ShouldHaveLength, 1)
			So(resp.Assigned[0].DroneHostname, ShouldEqual, serverID)
			So(resp.Assigned[0].DutId, ShouldEqual, newDutID)

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[0]
			p := "data/skylab/server_db.textpb"
			So(change.Files, ShouldContainKey, p)

			contents := change.Files[p]
			infra := &inventory.Infrastructure{}
			err = inventory.LoadInfrastructureFromString(contents, infra)
			So(err, ShouldBeNil)
			So(change.Subject, ShouldStartWith, "assign DUTs")
			So(infra.Servers, ShouldHaveLength, 2)

			var server *inventory.Server
			for _, s := range infra.Servers {
				if s.GetHostname() == serverID {
					server = s
					break
				}
			}
			So(server.DutUids, ShouldContain, existingDutID)
			So(server.DutUids, ShouldContain, newDutID)
		})

		Convey("AssignDutsToDrones with a new dut by name and existing drone assigns that dut.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: newDutID, DroneHostname: serverID},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.Assigned, ShouldHaveLength, 1)
			So(resp.Assigned[0].DroneHostname, ShouldEqual, serverID)
			So(resp.Assigned[0].DutId, ShouldEqual, newDutID)

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[0]
			p := "data/skylab/server_db.textpb"
			So(change.Files, ShouldContainKey, p)

			contents := change.Files[p]
			infra := &inventory.Infrastructure{}
			err = inventory.LoadInfrastructureFromString(contents, infra)
			So(err, ShouldBeNil)
			So(change.Subject, ShouldStartWith, "assign DUTs")
			So(infra.Servers, ShouldHaveLength, 2)

			var server *inventory.Server
			for _, s := range infra.Servers {
				if s.GetHostname() == serverID {
					server = s
					break
				}
			}
			So(server.DutUids, ShouldContain, existingDutID)
			So(server.DutUids, ShouldContain, newDutID)
		})

		Convey("AssignDutsToDrones with a new dut and no drone should pick a drone to assign.", func() {
			req := &fleet.AssignDutsToDronesRequest{
				Assignments: []*fleet.AssignDutsToDronesRequest_Item{
					{DutId: newDutID},
				},
			}
			resp, err := tf.Inventory.AssignDutsToDrones(tf.C, req)
			So(err, ShouldBeNil)
			So(resp, ShouldNotBeNil)
			So(resp.Assigned, ShouldHaveLength, 1)
			So(resp.Assigned[0].DroneHostname, ShouldEqual, serverID)
			So(resp.Assigned[0].DutId, ShouldEqual, newDutID)

			So(tf.FakeGerrit.Changes, ShouldHaveLength, 1)
			change := tf.FakeGerrit.Changes[0]
			p := "data/skylab/server_db.textpb"
			So(change.Files, ShouldContainKey, p)

			contents := change.Files[p]
			infra := &inventory.Infrastructure{}
			err = inventory.LoadInfrastructureFromString(contents, infra)
			So(err, ShouldBeNil)
			So(change.Subject, ShouldStartWith, "assign DUTs")
			So(infra.Servers, ShouldHaveLength, 2)

			var server *inventory.Server
			for _, s := range infra.Servers {
				if s.GetHostname() == serverID {
					server = s
					break
				}
			}
			So(server.DutUids, ShouldContain, existingDutID)
			So(server.DutUids, ShouldContain, newDutID)
		})
	})
}
