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

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/chromiumos/infra/proto/go/device"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
)

func TestGetDeviceConfig(t *testing.T) {
	ctx := testingContext()
	tf, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Get device config", t, func() {
		platformID := "coral"
		modelID := "mmm"
		variantID := "vvv"
		brandID := "bbb"
		gpuFamily := "GGG"
		id := DeviceConfigID{
			PlatformID: platformID,
			ModelID:    modelID,
			VariantID:  variantID,
			BrandID:    brandID,
		}
		configs := []testDeviceConfig{
			{
				dcID:      id,
				gpuFamily: gpuFamily,
			},
		}
		err := setDeviceConfigs(ctx, tf.FakeGitiles, configs)
		So(err, ShouldBeNil)

		deviceConfigs, err := GetDeviceConfig(ctx, tf.FakeGitiles)
		So(err, ShouldBeNil)
		dcID := getDeviceConfigIDStr(ctx, id)
		want := map[string]*device.Config{
			dcID: {
				Id: &device.ConfigId{
					PlatformId: &device.PlatformId{
						Value: platformID,
					},
					ModelId: &device.ModelId{
						Value: modelID,
					},
					VariantId: &device.VariantId{
						Value: variantID,
					},
					BrandId: &device.BrandId{
						Value: brandID,
					},
				},
				GpuFamily: gpuFamily,
			},
		}
		So(deviceConfigs, ShouldResemble, want)
	})
}

func TestSaveDeviceConfig(t *testing.T) {
	ctx := testingContext()
	_, validate := newTestFixtureWithContext(ctx, t)
	defer validate()
	Convey("Save device config", t, func() {
		id1 := DeviceConfigID{
			PlatformID: "board1",
			ModelID:    "model1",
			VariantID:  "variant1",
			BrandID:    "brand1",
		}
		id2 := DeviceConfigID{
			PlatformID: "board2",
			ModelID:    "model2",
			VariantID:  "variant2",
			BrandID:    "brand2",
		}
		deviceConfigs := fakeDeviceConfig(ctx, []DeviceConfigID{id1, id2})
		dcID1 := getDeviceConfigIDStr(ctx, id1)
		dcID2 := getDeviceConfigIDStr(ctx, id2)
		deviceConfigs[dcID1].GpuFamily = "gpu1"
		deviceConfigs[dcID2].GpuFamily = "gpu2"

		err := SaveDeviceConfig(ctx, deviceConfigs)
		So(err, ShouldBeNil)
		dc1 := deviceConfigEntity{ID: dcID1}
		if err = datastore.Get(ctx, &dc1); err != nil {
			t.Errorf("fail to get successful device by id %s", dcID1)
		}
		dc2 := deviceConfigEntity{ID: dcID2}
		if err = datastore.Get(ctx, &dc2); err != nil {
			t.Errorf("fail to get successful device by id %s", dcID2)
		}
		g1, err := getGpuFromDeviceConfigEntity(&dc1)
		if err != nil {
			t.Errorf(err.Error())
		}
		g2, err := getGpuFromDeviceConfigEntity(&dc2)
		if err != nil {
			t.Errorf(err.Error())
		}
		So(g1, ShouldEqual, "gpu1")
		So(g2, ShouldEqual, "gpu2")
	})
}

func getGpuFromDeviceConfigEntity(dce *deviceConfigEntity) (string, error) {
	var dc device.Config
	if err := proto.Unmarshal(dce.DeviceConfig, &dc); err != nil {
		return "", errors.Annotate(err, "fail to unmarshal device config for id %s", dce.ID).Err()
	}
	return dc.GetGpuFamily(), nil
}
