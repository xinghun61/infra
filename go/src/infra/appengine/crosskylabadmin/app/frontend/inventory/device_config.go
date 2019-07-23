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
	"bytes"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"

	"go.chromium.org/chromiumos/infra/proto/go/device"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"
)

// DeviceConfigID includes required info to form a device config ID.
type DeviceConfigID struct {
	PlatformID string
	ModelID    string
	VariantID  string
	BrandID    string
}

// getDeviceConfigIDStr generates device id for a DUT.
func getDeviceConfigIDStr(ctx context.Context, dcID DeviceConfigID) string {
	return strings.Join([]string{dcID.PlatformID, dcID.ModelID, dcID.VariantID, dcID.BrandID}, ".")
}

func getIDForDeviceConfig(ctx context.Context, dc *device.Config) string {
	return getDeviceConfigIDStr(ctx, DeviceConfigID{
		PlatformID: dc.Id.PlatformId.Value,
		ModelID:    dc.Id.ModelId.Value,
		VariantID:  dc.Id.VariantId.Value,
		BrandID:    dc.Id.BrandId.Value,
	})
}

func getIDForInventoryLabels(ctx context.Context, sl *inventory.SchedulableLabels) string {
	return getDeviceConfigIDStr(ctx, DeviceConfigID{
		PlatformID: sl.GetBoard(),
		ModelID:    sl.GetModel(),
		VariantID:  sl.GetSku(),
		BrandID:    sl.GetBrand(),
	})
}

// GetDeviceConfig fetch device configs from git.
func GetDeviceConfig(ctx context.Context, gitilesC gitiles.GitilesClient) (map[string]*device.Config, error) {
	cfg := config.Get(ctx).Inventory
	gf := gitstore.FilesSpec{
		Project: cfg.DeviceConfigProject,
		Branch:  cfg.DeviceConfigBranch,
		Paths:   []string{cfg.DeviceConfigPath},
	}
	files, err := gitstore.FetchFiles(ctx, gitilesC, gf)
	if err != nil {
		return nil, errors.Annotate(err, "fail to fetch device configs based on %s:%s:%v", gf.Project, gf.Branch, gf.Paths).Err()
	}
	data, ok := files[cfg.DeviceConfigPath]
	if !ok {
		return nil, errors.Reason("no device config in path %s/%s", cfg.DeviceConfigProject, cfg.DeviceConfigPath).Err()
	}

	unmarshaler := jsonpb.Unmarshaler{AllowUnknownFields: true}
	allConfigs := device.AllConfigs{}
	err = unmarshaler.Unmarshal(bytes.NewReader([]byte(data)), &allConfigs)
	if err != nil {
		return nil, errors.Annotate(err, "fail to unmarshal device config").Err()
	}
	deviceConfigs := make(map[string]*device.Config, 0)
	for _, c := range allConfigs.Configs {
		id := getIDForDeviceConfig(ctx, c)
		if _, found := deviceConfigs[id]; found {
			logging.Infof(ctx, "found duplicated id: %s id")
		} else {
			deviceConfigs[id] = c
		}
	}
	return deviceConfigs, nil
}
