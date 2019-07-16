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
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
)

const dut = `duts {
  common {
    environment: ENVIRONMENT_STAGING
    hostname: "dut_hostname"
    id: "dut_id_1"
    labels {
      capabilities {
        bluetooth: true
        carrier: CARRIER_INVALID
        gpu_family: "GGG"
        graphics: ""
        internal_display: true
        power: "battery"
        storage: "mmc"
        webcam: true
        touchpad: true
        video_acceleration: VIDEO_ACCELERATION_H264
        video_acceleration: VIDEO_ACCELERATION_ENC_H264
        video_acceleration: VIDEO_ACCELERATION_VP8
        video_acceleration: VIDEO_ACCELERATION_ENC_VP8
        video_acceleration: VIDEO_ACCELERATION_ENC_VP9
      }
      critical_pools: DUT_POOL_SUITES
      model: "link"
      peripherals {
        stylus: true
      }
    }
  }
}
`

func TestUpdateDeviceConfig(t *testing.T) {
	Convey("Update DUTs with empty device config", t, func() {
		ctx := testingContext()
		tf, validate := newTestFixtureWithContext(ctx, t)
		defer validate()
		deviceConfigs, err := GetDeviceConfig(ctx, tf.FakeGitiles)
		So(err, ShouldBeNil)
		tf.FakeGitiles.SetInventory(
			config.Get(ctx).Inventory,
			fakes.InventoryData{
				Lab: []byte(dut),
			},
		)

		store := gitstore.NewInventoryStore(tf.FakeGerrit, tf.FakeGitiles)
		err = store.Refresh(ctx)
		So(err, ShouldBeNil)
		url, err := updateDeviceConfig(tf.C, deviceConfigs, store)
		So(err, ShouldBeNil)
		So(url, ShouldNotContainSubstring, config.Get(ctx).Inventory.GerritHost)
	})
}
