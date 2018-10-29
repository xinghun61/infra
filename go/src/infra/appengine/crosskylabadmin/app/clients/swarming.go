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

// package clients exports wrappers for client side bindings for API used by
// crosskylabadmin app. These interfaces provide a way to fake/stub out the API
// calls for tests.
//
// The package is named clients instead of swarming etc because callers often
// need to also reference names from the underlying generated bindings.

package clients

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/golang/protobuf/ptypes/duration"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

const (
	// MaxConcurrentSwarmingCalls is the maximum number of concurrent swarming calls
	// made within the context of a single RPC call to this app.
	//
	// There is no per-instance limit (yet).
	MaxConcurrentSwarmingCalls = 10

	// DutIDDimensionKey identifies the swarming dimension containing the ID for
	// the DUT corresponding to a bot.
	DutIDDimensionKey = "dut_id"
	// DutModelDimensionKey identifies the swarming dimension containing the
	// Autotest model label for the DUT.
	DutModelDimensionKey = "label-model"
	// DutPoolDimensionKey identifies the swarming dimension containing the
	// Autotest pool label for the DUT.
	DutPoolDimensionKey = "label-pool"
	// DutStateDimensionKey identifies the swarming dimension containing the
	// autotest DUT state for a bot.
	DutStateDimensionKey = "dut_state"

	// PoolDimensionKey identifies the swarming pool dimension.
	PoolDimensionKey = "pool"
	// SwarmingTimeLayout is the layout used by swarming RPCs to specify timestamps.
	SwarmingTimeLayout = "2006-01-02T15:04:05.999999999"
)

// paginationChunkSize is the number of items requested in a single page in various
// Swarming RPC calls.
const paginationChunkSize = 100

// SwarmingClient exposes Swarming client API used by this package.
//
// In prod, a SwarmingClient for interacting with the Swarming service will be used.
// Tests should use a fake.
type SwarmingClient interface {
	ListAliveBotsInPool(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error)
	ListRecentTasks(c context.Context, tags []string, state string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error)
	ListSortedRecentTasksForBot(c context.Context, botID string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error)
	CreateTask(c context.Context, args *SwarmingCreateTaskArgs) (string, error)
}

// SwarmingCreateTaskArgs contains the arguments to SwarmingClient.CreateTask.
//
// This struct contains only a small subset of the Swarming task arguments that is needed by this app.
type SwarmingCreateTaskArgs struct {
	Cmd []string
	// The task targets a dut with the given dut id.
	DutID string
	// If non-empty, the task targets a dut in the given state.
	DutState             string
	ExecutionTimeoutSecs int64
	ExpirationSecs       int64
	Pool                 string
	Priority             int64
	Tags                 []string
}

type swarmingClientImpl swarming.Service

// NewSwarmingClient returns a SwarmingClient for interaction with the Swarming service.
func NewSwarmingClient(c context.Context, host string) (SwarmingClient, error) {
	// The Swarming call to list bots requires special previliges (beyond task trigger privilege)
	// This app is authorized to make those API calls.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get RPC transport for host %s", host).Err()
	}
	srv, err := swarming.New(&http.Client{Transport: t})
	if err != nil {
		return nil, errors.Annotate(err, "failed to create swarming client for host %s", host).Err()
	}
	srv.BasePath = fmt.Sprintf("https://%s/_ah/api/swarming/v1/", host)
	return (*swarmingClientImpl)(srv), nil
}

// ListAliveBotsInPool lists the Swarming bots in the given pool.
//
// Use dims to restrict to dimensions beyond pool.
func (sc *swarmingClientImpl) ListAliveBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	bis := []*swarming.SwarmingRpcsBotInfo{}
	dims.Set(PoolDimensionKey, pool)
	call := sc.Bots.List().Dimensions(dims.Format()...).IsDead("FALSE")
	for {
		ic, _ := context.WithTimeout(c, 60*time.Second)
		response, err := call.Context(ic).Do()
		if err != nil {
			return nil, errors.Reason("failed to list alive bots in pool %s", pool).InternalReason(err.Error()).Err()
		}
		bis = append(bis, response.Items...)
		if response.Cursor == "" {
			break
		}
		call = call.Cursor(response.Cursor)
	}
	return bis, nil
}

// CreateTask creates a Swarming task.
//
// On success, CreateTask returns the opaque task ID returned by Swarming.
func (sc *swarmingClientImpl) CreateTask(c context.Context, args *SwarmingCreateTaskArgs) (string, error) {
	dims := []*swarming.SwarmingRpcsStringPair{
		{
			Key:   DutIDDimensionKey,
			Value: args.DutID,
		},
		{
			Key:   PoolDimensionKey,
			Value: args.Pool,
		},
	}
	if args.DutState != "" {
		dims = append(dims, &swarming.SwarmingRpcsStringPair{
			Key:   DutStateDimensionKey,
			Value: args.DutState,
		})
	}

	ntr := &swarming.SwarmingRpcsNewTaskRequest{
		EvaluateOnly: false,
		// This is information only, but Swarming doesn't like it unset.
		Name:     "FleetAdminTask",
		Priority: args.Priority,
		Tags:     args.Tags,
		TaskSlices: []*swarming.SwarmingRpcsTaskSlice{
			{
				ExpirationSecs: args.ExpirationSecs,
				Properties: &swarming.SwarmingRpcsTaskProperties{
					Command:              args.Cmd,
					Dimensions:           dims,
					ExecutionTimeoutSecs: args.ExecutionTimeoutSecs,
					// We never want tasks deduplicated with ealier tasks.
					Idempotent: false,
				},
				// There are no fallback task slices.
				// Wait around until the first slice can run.
				WaitForCapacity: true,
			},
		},
	}
	ic, _ := context.WithTimeout(c, 60*time.Second)
	resp, err := sc.Tasks.New(ntr).Context(ic).Do()
	if err != nil {
		return "", errors.Reason("Failed to create task").InternalReason(err.Error()).Err()
	}
	return resp.TaskId, nil
}

// ListRecentTasks lists tasks with the given tags and in the given state.
//
// The most recent |limit| tasks are returned.
// state may be left "" to skip filtering by state.
func (sc *swarmingClientImpl) ListRecentTasks(c context.Context, tags []string, state string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error) {
	if limit < 0 {
		panic(fmt.Sprintf("limit set to %d which is < 0", limit))
	}

	trs := []*swarming.SwarmingRpcsTaskResult{}
	call := sc.Tasks.List().Tags(tags...)
	if state != "" {
		call.State(state)
	}

	// Limit() only limits the number of tasks returned in a single page. The
	// client must keep track of the total number returned across the calls.
	for {
		chunk := paginationChunkSize
		if limit < paginationChunkSize {
			chunk = limit
		}
		ic, _ := context.WithTimeout(c, 60*time.Second)
		resp, err := call.Limit(int64(chunk)).Context(ic).Do()
		if err != nil {
			return nil, errors.Reason("failed to list tasks with tags %s", strings.Join(tags, " ")).InternalReason(err.Error()).Err()
		}
		trs = append(trs, resp.Items...)
		if resp.Cursor == "" {
			break
		}
		call = call.Cursor(resp.Cursor)
	}
	return trs, nil
}

// ListSortedRecentTasksForBot lists the most recent tasks for the bot with given dutID.
//
// duration specifies how far in the back are the tasks allowed to have started. limit limits the number of tasks returned.
func (sc *swarmingClientImpl) ListSortedRecentTasksForBot(c context.Context, botID string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error) {
	trs := []*swarming.SwarmingRpcsTaskResult{}
	// TODO(pprabhu) These should really be sorted by STARTED_TS.
	// See crbug.com/857595 and crbug.com/857598
	call := sc.Bot.Tasks(botID).Sort("CREATED_TS")

	// Limit() only limits the number of tasks returned in a single page. The
	// client must keep track of the total number returned across the calls.
	for limit > 0 {
		chunk := paginationChunkSize
		if limit < paginationChunkSize {
			chunk = limit
		}
		ic, _ := context.WithTimeout(c, 60*time.Second)
		resp, err := call.Limit(int64(chunk)).Context(ic).Do()
		if err != nil {
			return nil, errors.Reason("failed to list tasks for dut %s", botID).InternalReason(err.Error()).Err()
		}
		trs = append(trs, resp.Items...)
		limit -= len(resp.Items)
		if resp.Cursor == "" {
			break
		}
		call = call.Cursor(resp.Cursor)
	}
	return trs, nil
}

// TimeSinceBotTask returns the duration.Duration elapsed since the given task completed on a bot.
//
// This function only considers tasks that were executed by Swarming to a specific bot. For tasks
// that were never executed on a bot, this function returns nil duration.
func TimeSinceBotTask(tr *swarming.SwarmingRpcsTaskResult) (*duration.Duration, error) {
	switch tr.State {
	case "RUNNING":
		return &duration.Duration{}, nil
	case "COMPLETED", "TIMED_OUT":
		// TIMED_OUT tasks are considered to have completed as opposed to
		// EXPIRED tasks, which set tr.AbandonedTs
		ts, err := time.Parse(SwarmingTimeLayout, tr.CompletedTs)
		if err != nil {
			return nil, errors.Annotate(err, "swarming returned corrupted completed timestamp %s", tr.CompletedTs).Err()
		}
		return google.NewDuration(time.Now().Sub(ts)), nil
	case "KILLED":
		ts, err := time.Parse(SwarmingTimeLayout, tr.AbandonedTs)
		if err != nil {
			return nil, errors.Annotate(err, "swarming returned corrupted abandoned timestamp %s", tr.AbandonedTs).Err()
		}
		return google.NewDuration(time.Now().Sub(ts)), nil
	case "BOT_DIED", "CANCELED", "EXPIRED", "NO_RESOURCE", "PENDING":
		// These states do not indicate any actual run of a task on the dut.
		break
	default:
		return nil, fmt.Errorf("unknown swarming task state %s", tr.State)
	}
	return nil, nil
}
