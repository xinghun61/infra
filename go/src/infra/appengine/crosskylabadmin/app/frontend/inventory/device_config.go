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
	"strings"

	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"

	"go.chromium.org/chromiumos/infra/proto/go/device"
)

// getDeviceConfigIDStr generates device id for a DUT.
func getDeviceConfigIDStr(ctx context.Context, platformID string, modelID string, variantID string, brandID string) string {
	return strings.Join([]string{platformID, modelID, variantID, brandID}, ".")
}

// GetDeviceConfig fetch device configs from git.
func GetDeviceConfig(ctx context.Context, gitilesC gitiles.GitilesClient) (map[string]*device.Config, error) {
	// TODO(xixuan): to be implemented.
	deviceConfigs := make(map[string]*device.Config, 0)
	return deviceConfigs, nil
}
