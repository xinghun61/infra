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
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/data/stringset"
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
