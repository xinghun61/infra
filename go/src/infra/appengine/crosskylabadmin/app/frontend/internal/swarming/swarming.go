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

// Package swarming contains utilities for skylab swarming tasks.
package swarming

import (
	"context"
	"fmt"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"

	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"net/url"
)

const (
	// taskUser is the user for tasks created by Tasker.
	taskUser = "admin-service"
)

// URLForTask returns the task URL for a given task ID.
func URLForTask(ctx context.Context, tid string) string {
	cfg := config.Get(ctx)
	u := url.URL{
		Scheme: "https",
		Host:   cfg.Swarming.Host,
		Path:   "task",
	}
	q := u.Query()
	q.Set("id", tid)
	u.RawQuery = q.Encode()
	return u.String()
}

// AddCommonTags adds some Swarming tags common to all Skylab admin tasks.
func AddCommonTags(ctx context.Context, ts ...string) []string {
	cfg := config.Get(ctx)
	tags := make([]string, 0, len(ts)+2)
	tags = append(tags, cfg.Swarming.LuciProjectTag)
	tags = append(tags, cfg.Swarming.FleetAdminTaskTag)
	tags = append(tags, ts...)
	return tags
}

// SetCommonTaskArgs sets Swarming task arguments common to all Skylab admin tasks.
func SetCommonTaskArgs(ctx context.Context, args *clients.SwarmingCreateTaskArgs) *clients.SwarmingCreateTaskArgs {
	cfg := config.Get(ctx)
	args.User = taskUser
	args.ServiceAccount = cfg.Tasker.AdminTaskServiceAccount
	args.Pool = cfg.Swarming.BotPool
	return args
}

// ExtractSingleValuedDimension extracts one specified dimension from a dimension slice.
func ExtractSingleValuedDimension(dims strpair.Map, key string) (string, error) {
	vs, ok := dims[key]
	if !ok {
		return "", fmt.Errorf("failed to find dimension %s", key)
	}
	switch len(vs) {
	case 1:
		return vs[0], nil
	case 0:
		return "", fmt.Errorf("no value for dimension %s", key)
	default:
		return "", fmt.Errorf("multiple values for dimension %s", key)
	}
}

// DimensionsMap converts swarming bot dimensions to a map.
func DimensionsMap(sdims []*swarming.SwarmingRpcsStringListPair) strpair.Map {
	dims := make(strpair.Map)
	for _, sdim := range sdims {
		dims[sdim.Key] = sdim.Value
	}
	return dims
}
