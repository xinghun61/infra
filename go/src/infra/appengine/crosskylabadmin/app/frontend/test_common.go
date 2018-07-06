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

package frontend

import (
	"fmt"
	"sort"
	"sync"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
)

// fakeSwarmingClient implements SwarmingClient.
type fakeSwarmingClient struct {
	m sync.Mutex
	// pool is the single common pool that all bots belong to.
	pool string

	// botInfos maps the dut_id for a bot to its swarming.SwarmingRpcsBotInfo
	botInfos map[string]*swarming.SwarmingRpcsBotInfo
	// botTasks maps the bot_id for a bot to the known tasks for the bot.
	botTasks map[string][]*swarming.SwarmingRpcsTaskResult

	// taskArgs accumulates the arguments to CreateTask calls on fakeSwarmingClient
	taskArgs []*clients.SwarmingCreateTaskArgs
	// nextTaskID is used to construct the next task ID to be returned from CreateTask()
	nextTaskID int
	// taskIDs accumulates the generated Swarming task ids by CreateTask calls.
	taskIDs map[*clients.SwarmingCreateTaskArgs]string
}

// ResetTasks clears away cached information about created tasks.
func (fsc *fakeSwarmingClient) ResetTasks() {
	fsc.taskArgs = []*clients.SwarmingCreateTaskArgs{}
	fsc.taskIDs = map[*clients.SwarmingCreateTaskArgs]string{}
}

// ListAliveBotsInPool is a fake implementation of SwarmingClient.ListAliveBotsInPool.
//
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
//
// Default values are used for other dimensions / tasks for the bot.
func (fsc *fakeSwarmingClient) setAvailableDutIDs(duts []string) {
	fsc.botInfos = make(map[string]*swarming.SwarmingRpcsBotInfo)
	fsc.botTasks = make(map[string][]*swarming.SwarmingRpcsTaskResult)
	for _, d := range duts {
		fsc.botInfos[d] = &swarming.SwarmingRpcsBotInfo{
			BotId: fmt.Sprintf("bot_%s", d),
			Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{
					Key:   "dut_id",
					Value: []string{d},
				},
				{
					Key:   "dut_state",
					Value: []string{"ready"},
				},
			},
		}
	}
}

// CreateTask stores the arguments to the CreateTask call in fsc and returns unique task IDs.
func (fsc *fakeSwarmingClient) CreateTask(c context.Context, args *clients.SwarmingCreateTaskArgs) (string, error) {
	fsc.m.Lock()
	defer fsc.m.Unlock()
	fsc.taskArgs = append(fsc.taskArgs, args)
	tid := fmt.Sprintf("fake_task_%d", fsc.nextTaskID)
	fsc.nextTaskID = fsc.nextTaskID + 1
	fsc.taskIDs[args] = tid
	return tid, nil
}

// ListRecentTasks is a simplistic implementation of SwarmingClient.ListRecentTasks.
//
// This function simply returns all created tasks in the requested state (default: PENDING)
func (fsc *fakeSwarmingClient) ListRecentTasks(c context.Context, tags []string, state string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error) {
	fsc.m.Lock()
	defer fsc.m.Unlock()

	if state == "" {
		state = "PENDING"
	}
	trs := []*swarming.SwarmingRpcsTaskResult{}
	for _, ta := range fsc.taskArgs {
		if tagsMatch(tags, ta.Tags) {
			trs = append(trs, &swarming.SwarmingRpcsTaskResult{
				State:  state,
				Tags:   tags,
				TaskId: fsc.taskIDs[ta],
			})
		}
	}
	return trs, nil
}

func (fsc *fakeSwarmingClient) ListSortedRecentTasksForBot(c context.Context, botID string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error) {
	return fsc.botTasks[botID], nil
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

// tagsMatch returns true if ts1 and ts2 contain the same tags.
func tagsMatch(ts1 []string, ts2 []string) bool {
	if len(ts1) != len(ts2) {
		return false
	}
	sort.Strings(ts1)
	sort.Strings(ts2)
	for i := range ts1 {
		if ts1[i] != ts2[i] {
			return false
		}
	}
	return true
}
