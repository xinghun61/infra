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
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/chromiumos/infra/proto/go/device"
	"golang.org/x/net/context"

	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
)

const (
	gpu = "fakeGPU"
	// dut should follow the following rules:
	// 1) entries should be in alphabetical order.
	// 2) indent is 2 spaces, no tabs.
	dut = `duts {
  common {
    environment: ENVIRONMENT_STAGING
    hostname: "dut_hostname"
    id: "dut_id_1"
    labels {
      capabilities {
        carrier: CARRIER_INVALID
        gpu_family: "%s"
        graphics: ""
        power: ""
        storage: ""
      }
      critical_pools: DUT_POOL_SUITES
      model: "link"
      peripherals {
      }
    }
  }
}
`
)

func fakeDeviceConfig(ctx context.Context, id DeviceConfigID) map[string]*device.Config {
	dcID := getDeviceConfigIDStr(ctx, id)
	return map[string]*device.Config{
		dcID: {
			Id: &device.ConfigId{
				PlatformId: &device.PlatformId{
					Value: id.PlatformID,
				},
				ModelId: &device.ModelId{
					Value: id.ModelID,
				},
				VariantId: &device.VariantId{
					Value: id.VariantID,
				},
				BrandId: &device.BrandId{
					Value: id.BrandID,
				},
			},
			GpuFamily: gpu,
		},
	}
}

func TestUpdateDeviceConfig(t *testing.T) {
	Convey("Update DUTs with empty device config", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		deviceConfigs := map[string]*device.Config{}
		tf.FakeGitiles.SetInventory(
			config.Get(ctx).Inventory,
			fakes.InventoryData{
				Lab: []byte(fmt.Sprintf(dut, gpu)),
			},
		)
		store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
		err := store.Refresh(ctx)
		So(err, ShouldBeNil)
		url, err := updateDeviceConfig(tf.C, deviceConfigs, store)
		So(err, ShouldBeNil)
		So(url, ShouldNotContainSubstring, config.Get(ctx).Inventory.GerritHost)
	})

	Convey("Update DUTs as device config changes", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		id := DeviceConfigID{
			PlatformID: "",
			ModelID:    "link",
			VariantID:  "",
			BrandID:    "",
		}
		deviceConfigs := fakeDeviceConfig(ctx, id)

		err := tf.FakeGitiles.SetInventory(config.Get(ctx).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname", "link", "DUT_POOL_SUITES"},
			}),
		})
		store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
		err = store.Refresh(ctx)
		So(err, ShouldBeNil)
		url, err := updateDeviceConfig(tf.C, deviceConfigs, store)
		So(err, ShouldBeNil)
		So(url, ShouldContainSubstring, config.Get(ctx).Inventory.GerritHost)
	})

	Convey("Update DUTs with non-existing device config", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		id := DeviceConfigID{
			PlatformID: "",
			ModelID:    "non-link",
			VariantID:  "",
			BrandID:    "",
		}
		deviceConfigs := fakeDeviceConfig(ctx, id)
		err := tf.FakeGitiles.SetInventory(config.Get(ctx).Inventory, fakes.InventoryData{
			Lab: inventoryBytesFromDUTs([]testInventoryDut{
				{"dut_id_1", "dut_hostname", "link", "DUT_POOL_SUITES"},
			}),
		})
		So(err, ShouldBeNil)
		store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
		err = store.Refresh(ctx)
		So(err, ShouldBeNil)
		url, err := updateDeviceConfig(tf.C, deviceConfigs, store)
		So(err, ShouldBeNil)
		So(url, ShouldNotContainSubstring, config.Get(ctx).Inventory.GerritHost)
	})

	Convey("Update DUTs with exactly same device config", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		id := DeviceConfigID{
			PlatformID: "",
			ModelID:    "link",
			VariantID:  "",
			BrandID:    "",
		}
		deviceConfigs := fakeDeviceConfig(ctx, id)
		err := tf.FakeGitiles.SetInventory(
			config.Get(ctx).Inventory, fakes.InventoryData{
				Lab: []byte(fmt.Sprintf(dut, gpu)),
			},
		)
		So(err, ShouldBeNil)
		store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
		err = store.Refresh(ctx)
		So(err, ShouldBeNil)
		url, err := updateDeviceConfig(tf.C, deviceConfigs, store)
		So(err, ShouldBeNil)
		So(url, ShouldNotContainSubstring, config.Get(ctx).Inventory.GerritHost)
	})
}
