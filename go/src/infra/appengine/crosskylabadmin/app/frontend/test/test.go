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

package test

import (
	"fmt"
	"strings"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	"go.chromium.org/luci/common/data/strpair"
	"golang.org/x/net/context"
)

// FakeListAliveBotsInPool returns a function that implements
// SwarmingClient.ListAliveBotsInPool.
//
// This fake implementation captures the bots argument and returns a subset of
// the bots filtered by the dimensions argument in the
// SwarmingClient.ListAliveBotsInPool call.
// TODO(xixuan): remove the duplication in package frontend.
func FakeListAliveBotsInPool(bots []*swarming.SwarmingRpcsBotInfo) func(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	return func(_ context.Context, _ string, ds strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
		resp := []*swarming.SwarmingRpcsBotInfo{}
		for _, b := range bots {
			if botContainsDims(b, ds) {
				resp = append(resp, b)
			}
		}
		return resp, nil
	}
}

// botContainsDims determines if the bot b satisfies the requirements specified
// via dims
// TODO(xixuan): remove the duplication in package frontend.
func botContainsDims(b *swarming.SwarmingRpcsBotInfo, dims strpair.Map) bool {
	bdm := strpair.Map{}
	for _, bds := range b.Dimensions {
		bdm[bds.Key] = bds.Value
	}
	for key, values := range dims {
		for _, value := range values {
			if !bdm.Contains(key, value) {
				return false
			}
		}
	}
	return true
}

// BotForDUT returns BotInfos for DUTs with the given dut id.
//
// state is the bot's state dimension.
// dims is a convenient way to specify other bot dimensions.
// "a:x,y;b:z" will set the dimensions of the bot to ["a": ["x", "y"], "b":
//   ["z"]]
// TODO(xixuan): remove the duplication in package frontend.
func BotForDUT(id string, state string, dims string) *swarming.SwarmingRpcsBotInfo {
	sdims := make([]*swarming.SwarmingRpcsStringListPair, 0, 2)
	if dims != "" {
		ds := strings.Split(dims, ";")
		for _, d := range ds {
			d = strings.Trim(d, " ")
			kvs := strings.Split(d, ":")
			if len(kvs) != 2 {
				panic(fmt.Sprintf("dims string |%s|%s has a non-keyval dimension |%s|", dims, ds, d))
			}
			sdim := &swarming.SwarmingRpcsStringListPair{
				Key:   strings.Trim(kvs[0], " "),
				Value: []string{},
			}
			for _, v := range strings.Split(kvs[1], ",") {
				sdim.Value = append(sdim.Value, strings.Trim(v, " "))
			}
			sdims = append(sdims, sdim)
		}
	}
	sdims = append(sdims, &swarming.SwarmingRpcsStringListPair{
		Key:   "dut_state",
		Value: []string{state},
	})
	sdims = append(sdims, &swarming.SwarmingRpcsStringListPair{
		Key:   "dut_id",
		Value: []string{id},
	})
	sdims = append(sdims, &swarming.SwarmingRpcsStringListPair{
		Key:   "dut_name",
		Value: []string{id + "-host"},
	})
	return &swarming.SwarmingRpcsBotInfo{
		BotId:      fmt.Sprintf("bot_%s", id),
		Dimensions: sdims,
	}
}
