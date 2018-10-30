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
	"testing"

	"github.com/golang/mock/gomock"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/proto/google"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/clients/mock"
	"infra/appengine/crosskylabadmin/app/config"
)

type testFixture struct {
	C       context.Context
	Tracker fleet.TrackerServer
	Tasker  fleet.TaskerServer

	// Deprecated. New tests should use MockSwarming instead.
	FakeSwarming *fakeSwarmingClient
	MockSwarming *mock.MockSwarmingClient
}

// newTextFixtureWithFakeSwarming creates a new testFixture to be used in unittests.
// The function returns the created testFixture and cleanup function that must be deferred by the caller.
//
// This is a transitional function while existing tests are in migration.
// New tests should use newTestFixture instead.
func newTestFixtureWithFakeSwarming(_ *testing.T) (testFixture, func()) {
	tf := testFixture{}
	tf.C = testingContext()
	tf.FakeSwarming = &fakeSwarmingClient{
		pool:    config.Get(tf.C).Swarming.BotPool,
		taskIDs: map[*clients.SwarmingCreateTaskArgs]string{},
	}
	tf.Tracker = &TrackerServerImpl{
		ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return tf.FakeSwarming, nil
		},
	}
	tf.Tasker = &TaskerServerImpl{
		ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return tf.FakeSwarming, nil
		},
	}
	return tf, func() {}
}

// newTextFixture creates a new testFixture to be used in unittests.
// The function returns the created testFixture and cleanup function that must be deferred by the caller.
func newTestFixture(t *testing.T) (testFixture, func()) {
	tf := testFixture{}
	tf.C = testingContext()

	mc := gomock.NewController(t)
	tf.MockSwarming = mock.NewMockSwarmingClient(mc)
	tf.Tracker = &TrackerServerImpl{
		ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return tf.MockSwarming, nil
		},
	}
	tf.Tasker = &TaskerServerImpl{
		ClientFactory: func(context.Context, string) (clients.SwarmingClient, error) {
			return tf.MockSwarming, nil
		},
	}

	cleanup := func() {
		mc.Finish()
	}
	return tf, cleanup
}

func testingContext() context.Context {
	c := gaetesting.TestingContextWithAppID("dev~infra-crosskylabadmin")
	c = config.Use(c, &config.Config{
		AccessGroup: "fake-access-group",
		Swarming: &config.Swarming{
			Host:              "https://fake-host.appspot.com",
			BotPool:           "ChromeOSSkylab",
			FleetAdminTaskTag: "fake-tag",
			LuciProjectTag:    "fake-project",
		},
		Tasker: &config.Tasker{
			BackgroundTaskExecutionTimeoutSecs: 3600,
			BackgroundTaskExpirationSecs:       300,
		},
		Cron: &config.Cron{
			FleetAdminTaskPriority:     33,
			EnsureTasksCount:           3,
			RepairIdleDuration:         google.NewDuration(10),
			RepairAttemptDelayDuration: google.NewDuration(10),
		},
	})
	datastore.GetTestable(c).Consistent(true)
	return c
}

// readyBotsForDutIDs returns BotInfos for DUTs with the given dut ids in "ready" state.
func readyBotsForDutIDs(ids []string) []*swarming.SwarmingRpcsBotInfo {
	bis := make([]*swarming.SwarmingRpcsBotInfo, 0, len(ids))
	for _, id := range ids {
		bis = append(bis, &swarming.SwarmingRpcsBotInfo{
			BotId: fmt.Sprintf("bot_%s", id),
			Dimensions: []*swarming.SwarmingRpcsStringListPair{
				{
					Key:   "dut_id",
					Value: []string{id},
				},
				{
					Key:   "dut_state",
					Value: []string{"ready"},
				},
			},
		})
	}
	return bis
}

// setBotDimension sets the dimension with given key to values.
func setBotDimension(b *swarming.SwarmingRpcsBotInfo, key string, values []string) {
	for _, keyval := range b.Dimensions {
		if keyval.Key == key {
			keyval.Value = values
			return
		}
	}
	b.Dimensions = append(b.Dimensions, &swarming.SwarmingRpcsStringListPair{
		Key:   key,
		Value: values,
	})
}

// fakeListAliveBotsInPool returns a function that implements SwarmingClient.ListAliveBotsInPool.
//
// This fake implementation captures the bots argument and returns a subset of the bots
// filtered by the dimensions argument in the SwarmingClient.ListAliveBotsInPool call.
func fakeListAliveBotsInPool(bots []*swarming.SwarmingRpcsBotInfo) func(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
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

// botContainsDims determines if the bot b satisfies the requirements specified via dims
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

// ///////// TODO(pprabhu) Stop using fakeSwarmingClient and delete everything below

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
