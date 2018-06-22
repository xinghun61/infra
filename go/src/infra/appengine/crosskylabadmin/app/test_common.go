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

package app

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"sync"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"golang.org/x/net/context"
)

// fakeSwarmingClient implements SwarmingClient.
type fakeSwarmingClient struct {
	m sync.Mutex
	// pool is the single common pool that all bots belong to.
	pool string

	// botInfo maps the dut_id for a bot to its swarming.SwarmingRpcsBotInfo
	botInfos map[string]*swarming.SwarmingRpcsBotInfo
	// taskArgs accumulates the arguments to CreateTask calls on fakeSwarmingClient
	taskArgs []*SwarmingCreateTaskArgs

	// nextTaskID is used to construct the next task ID to be returned from CreateTask()
	nextTaskID int
}

// ListAliveBotsInPool is a fake implementation of SwarmingClient.ListAliveBotsInPool.
// This function is intentionally simple. It only supports filtering by dut_id dimension.
func (fsc *fakeSwarmingClient) ListAliveBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	resp := []*swarming.SwarmingRpcsBotInfo{}
	if pool != fsc.pool {
		return resp, nil
	}
	switch len(dims) {
	case 0:
		for _, bi := range fsc.botInfos {
			resp = append(resp, bi)
		}
	case 1:
		k := dims.Get("dut_id")
		if k == "" {
			panic(fmt.Sprintf("got dims %s, want a single key: dut_id", dims))
		}
		bi, ok := fsc.botInfos[k]
		if ok {
			resp = append(resp, bi)
		}
	}
	return resp, nil
}

// setAvailableDutIDs sets the bot list returned by fakeSwarmingClient.ListAliveBotsInPool
// to be the bots corresponding to the given dut IDs.
func (fsc *fakeSwarmingClient) setAvailableDutIDs(duts []string) {
	fsc.botInfos = make(map[string]*swarming.SwarmingRpcsBotInfo)
	for _, d := range duts {
		fsc.botInfos[d] = &swarming.SwarmingRpcsBotInfo{
			BotId: fmt.Sprintf("bot_%s", d),
			Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{
					Key:   "dut_id",
					Value: []string{d},
				},
			},
		}
	}
}

// CreateTask stores the arguments to the CreateTask call in fsc and returns unique task IDs.
func (fsc *fakeSwarmingClient) CreateTask(c context.Context, args *SwarmingCreateTaskArgs) (string, error) {
	fsc.m.Lock()
	defer fsc.m.Unlock()
	fsc.taskArgs = append(fsc.taskArgs, args)
	tid := fmt.Sprintf("fake_task_%d", fsc.nextTaskID)
	fsc.nextTaskID = fsc.nextTaskID + 1
	return tid, nil
}

// makeBotSelector returns a fleet.BotSelector selecting each of the duts
// recognized by the given Dut IDs.
func makeBotSelectorForDuts(duts []string) []*fleet.BotSelector {
	var bs []*fleet.BotSelector
	for _, d := range duts {
		bs = append(bs, &fleet.BotSelector{DutId: d})
	}
	return bs
}
