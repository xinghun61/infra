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

	"go.chromium.org/chromiumos/infra/proto/go/device"
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
