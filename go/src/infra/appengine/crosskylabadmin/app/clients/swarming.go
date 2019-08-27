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

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"

	"github.com/golang/protobuf/ptypes/duration"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

const (
	// MaxConcurrentSwarmingCalls is the maximum number of concurrent swarming
	// calls made within the context of a single RPC call to this app.
	//
	// There is no per-instance limit (yet).
	MaxConcurrentSwarmingCalls = 20

	// DutIDDimensionKey identifies the swarming dimension containing the ID for
	// the DUT corresponding to a bot.
	DutIDDimensionKey = "dut_id"
	// DutModelDimensionKey identifies the swarming dimension containing the
	// Autotest model label for the DUT.
	DutModelDimensionKey = "label-model"
	// DutPoolDimensionKey identifies the swarming dimension containing the
	// Autotest pool label for the DUT.
	DutPoolDimensionKey = "label-pool"
	// DutOSDimensionKey identifies the swarming dimension containing the
	// OS label for the DUT.
	DutOSDimensionKey = "label-os_type"
	// DutNameDimensionKey identifies the swarming dimension
	// containing the DUT name.
	DutNameDimensionKey = "dut_name"
	// DutStateDimensionKey identifies the swarming dimension containing the
	// autotest DUT state for a bot.
	DutStateDimensionKey = "dut_state"

	// PoolDimensionKey identifies the swarming pool dimension.
	PoolDimensionKey = "pool"
	// SwarmingTimeLayout is the layout used by swarming RPCs to specify timestamps.
	SwarmingTimeLayout = "2006-01-02T15:04:05.999999999"
)

// paginationChunkSize is the number of items requested in a single page in
// various Swarming RPC calls.
const paginationChunkSize = 100

// SwarmingClient exposes Swarming client API used by this package.
//
// In prod, a SwarmingClient for interacting with the Swarming service will be
// used. Tests should use a fake.
type SwarmingClient interface {
	ListAliveIdleBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error)
	ListAliveBotsInPool(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error)
	ListBotTasks(id string) BotTasksCursor
	ListRecentTasks(c context.Context, tags []string, state string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error)
	ListSortedRecentTasksForBot(c context.Context, botID string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error)
	CreateTask(c context.Context, name string, args *SwarmingCreateTaskArgs) (string, error)
	GetTaskResult(ctx context.Context, tid string) (*swarming.SwarmingRpcsTaskResult, error)
}

// SwarmingCreateTaskArgs contains the arguments to SwarmingClient.CreateTask.
//
// This struct contains only a small subset of the Swarming task arguments that
// is needed by this app.
type SwarmingCreateTaskArgs struct {
	Cmd []string
	// The task targets a dut with the given dut id.
	DutID string
	// If non-empty, the task targets a dut in the given state.
	DutState             string
	DutName              string
	ExecutionTimeoutSecs int64
	ExpirationSecs       int64
	Pool                 string
	Priority             int64
	Tags                 []string
	User                 string
	ServiceAccount       string
}

type swarmingClientImpl swarming.Service

// NewSwarmingClient returns a SwarmingClient for interaction with the Swarming
// service.
func NewSwarmingClient(c context.Context, host string) (SwarmingClient, error) {
	// The Swarming call to list bots requires special previliges (beyond task
	// trigger privilege) This app is authorized to make those API calls.
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

// ListAliveIdleBotsInPool lists the Swarming bots in the given pool.
//
// Use dims to restrict to dimensions beyond pool.
func (sc *swarmingClientImpl) ListAliveIdleBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	var botsInfo []*swarming.SwarmingRpcsBotInfo
	dims.Set(PoolDimensionKey, pool)
	call := sc.Bots.List().Dimensions(dims.Format()...).IsDead("FALSE").IsBusy("FALSE")
	for {
		ic, _ := context.WithTimeout(c, 60*time.Second)
		response, err := call.Context(ic).Do()
		if err != nil {
			return nil, errors.Reason("failed to list alive and idle bots in pool %s", pool).InternalReason(err.Error()).Err()
		}
		botsInfo = append(botsInfo, response.Items...)
		if response.Cursor == "" {
			break
		}
		call = call.Cursor(response.Cursor)
	}
	return botsInfo, nil
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
func (sc *swarmingClientImpl) CreateTask(c context.Context, name string, args *SwarmingCreateTaskArgs) (string, error) {
	if args.DutID == "" && args.DutName == "" {
		return "", errors.Reason("invalid argument: one of (DutID, DutName) need to be specified").Err()
	}
	dims := []*swarming.SwarmingRpcsStringPair{
		{
			Key:   PoolDimensionKey,
			Value: args.Pool,
		},
	}
	if args.DutID != "" {
		dims = append(dims, &swarming.SwarmingRpcsStringPair{
			Key:   DutIDDimensionKey,
			Value: args.DutID,
		})
	}
	if args.DutName != "" {
		dims = append(dims, &swarming.SwarmingRpcsStringPair{
			Key:   DutNameDimensionKey,
			Value: args.DutName,
		})
	}
	if args.DutState != "" {
		dims = append(dims, &swarming.SwarmingRpcsStringPair{
			Key:   DutStateDimensionKey,
			Value: args.DutState,
		})
	}

	ntr := &swarming.SwarmingRpcsNewTaskRequest{
		EvaluateOnly: false,
		Name:         name,
		Priority:     args.Priority,
		Tags:         args.Tags,
		TaskSlices: []*swarming.SwarmingRpcsTaskSlice{
			{
				ExpirationSecs: args.ExpirationSecs,
				Properties: &swarming.SwarmingRpcsTaskProperties{
					Command:              args.Cmd,
					Dimensions:           dims,
					ExecutionTimeoutSecs: args.ExecutionTimeoutSecs,
					// We never want tasks deduplicated with earlier tasks.
					Idempotent: false,
				},
				// There are no fallback task slices.
				// Wait around until the first slice can run.
				WaitForCapacity: true,
			},
		},
		User:           args.User,
		ServiceAccount: args.ServiceAccount,
	}
	ic, _ := context.WithTimeout(c, 60*time.Second)
	resp, err := sc.Tasks.New(ntr).Context(ic).Do()
	if err != nil {
		return "", errors.Reason("Failed to create task").InternalReason(err.Error()).Err()
	}
	return resp.TaskId, nil
}

// GetTaskResult gets the task result for a given task ID.
func (sc *swarmingClientImpl) GetTaskResult(ctx context.Context, tid string) (*swarming.SwarmingRpcsTaskResult, error) {
	call := sc.Task.Result(tid)
	ctx, _ = context.WithTimeout(ctx, 60*time.Second)
	resp, err := call.Context(ctx).Do()
	if err != nil {
		return nil, errors.Reason("failed to get result for task %s", tid).InternalReason(err.Error()).Err()
	}
	return resp, nil
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
	p := Pager{Remaining: limit}
	for {
		chunk := p.Next()
		if chunk == 0 {
			break
		}
		ic, _ := context.WithTimeout(c, 60*time.Second)
		resp, err := call.Limit(int64(chunk)).Context(ic).Do()
		if err != nil {
			return nil, errors.Reason("failed to list tasks with tags %s", strings.Join(tags, " ")).InternalReason(err.Error()).Err()
		}
		trs = append(trs, resp.Items...)
		p.Record(len(resp.Items))
		if resp.Cursor == "" {
			break
		}
		call = call.Cursor(resp.Cursor)
	}
	return trs, nil
}

// BotTasksCursor tracks a paginated query for Swarming bot tasks.
type BotTasksCursor interface {
	Next(context.Context, int64) ([]*swarming.SwarmingRpcsTaskResult, error)
}

// botTasksCursorImpl tracks a paginated query for Swarming bot tasks.
type botTasksCursorImpl struct {
	description string
	call        *swarming.BotTasksCall
	done        bool
}

// Next returns at most the next N tasks from the task cursor.
func (c *botTasksCursorImpl) Next(ctx context.Context, n int64) ([]*swarming.SwarmingRpcsTaskResult, error) {
	if c.done || n < 1 {
		return nil, nil
	}
	ctx, cancel := context.WithTimeout(ctx, 60*time.Second)
	defer cancel()
	resp, err := c.call.Limit(n).Context(ctx).Do()
	if err != nil {
		return nil, errors.Reason("failed to list %s", c.description).InternalReason(err.Error()).Err()
	}
	if resp.Cursor != "" {
		c.call.Cursor(resp.Cursor)
	} else {
		c.done = true
	}
	return resp.Items, nil
}

// ListBotTasks lists the bot's tasks.  Since the query is paginated,
// this function returns a TaskCursor that the caller can iterate on.
func (sc *swarmingClientImpl) ListBotTasks(id string) BotTasksCursor {
	// TODO(pprabhu): These should really be sorted by STARTED_TS.
	// See crbug.com/857595 and crbug.com/857598
	call := sc.Bot.Tasks(id).Sort("CREATED_TS")
	return &botTasksCursorImpl{
		description: fmt.Sprintf("tasks for bot %s", id),
		call:        call,
	}
}

// ListSortedRecentTasksForBot lists the most recent tasks for the bot with
// given dutID.
//
// duration specifies how far in the back are the tasks allowed to have
// started. limit limits the number of tasks returned.
func (sc *swarmingClientImpl) ListSortedRecentTasksForBot(ctx context.Context, botID string, limit int) ([]*swarming.SwarmingRpcsTaskResult, error) {
	var trs []*swarming.SwarmingRpcsTaskResult
	c := sc.ListBotTasks(botID)
	p := Pager{Remaining: limit}
	for {
		chunk := p.Next()
		if chunk == 0 {
			break
		}
		trs2, err := c.Next(ctx, int64(chunk))
		if err != nil {
			return nil, err
		}
		if len(trs2) == 0 {
			break
		}
		p.Record(len(trs2))
		trs = append(trs, trs2...)
	}
	return trs, nil
}

// TimeSinceBotTask calls TimeSinceBotTaskN with time.Now().
func TimeSinceBotTask(tr *swarming.SwarmingRpcsTaskResult) (*duration.Duration, error) {
	return TimeSinceBotTaskN(tr, time.Now())
}

// TimeSinceBotTaskN returns the duration.Duration elapsed since the given task
// completed on a bot.
//
// This function only considers tasks that were executed by Swarming to a
// specific bot. For tasks that were never executed on a bot, this function
// returns nil duration.
func TimeSinceBotTaskN(tr *swarming.SwarmingRpcsTaskResult, now time.Time) (*duration.Duration, error) {
	if tr.State == "RUNNING" {
		return &duration.Duration{}, nil
	}
	t, err := TaskDoneTime(tr)
	if err != nil {
		return nil, errors.Annotate(err, "get time since bot task").Err()
	}
	if t.IsZero() {
		return nil, nil
	}
	return google.NewDuration(now.Sub(t)), nil
}

// TaskDoneTime returns the time when the given task completed on a
// bot.  If the task was never run or is still running, this function
// returns a zero time.
func TaskDoneTime(tr *swarming.SwarmingRpcsTaskResult) (time.Time, error) {
	switch tr.State {
	case "RUNNING":
		return time.Time{}, nil
	case "COMPLETED", "TIMED_OUT":
		// TIMED_OUT tasks are considered to have completed as opposed to EXPIRED
		// tasks, which set tr.AbandonedTs
		t, err := time.Parse(SwarmingTimeLayout, tr.CompletedTs)
		if err != nil {
			return time.Time{}, errors.Annotate(err, "get task done time").Err()
		}
		return t, nil
	case "KILLED":
		t, err := time.Parse(SwarmingTimeLayout, tr.AbandonedTs)
		if err != nil {
			return time.Time{}, errors.Annotate(err, "get task done time").Err()
		}
		return t, nil
	case "BOT_DIED", "CANCELED", "EXPIRED", "NO_RESOURCE", "PENDING":
		// These states do not indicate any actual run of a task on the dut.
		return time.Time{}, nil
	default:
		return time.Time{}, errors.Reason("get task done time: unknown task state %s", tr.State).Err()
	}
}

// Pager manages pagination of API calls.
type Pager struct {
	// Remaining is set to the number of items to retrieve.  This
	// can be modified after Pager has been used, but not
	// concurrently.
	Remaining int
}

// Next returns the number of items to request.  If there are no more
// items to request, returns 0.
func (p *Pager) Next() int {
	switch {
	case p.Remaining < 0:
		return 0
	case p.Remaining < paginationChunkSize:
		return p.Remaining
	default:
		return paginationChunkSize
	}
}

// Record records that items have been received (since a request may
// not return the exact number of items requested).
func (p *Pager) Record(n int) {
	p.Remaining -= n
}

// GetStateDimension gets the dut_state value from a dimension slice.
func GetStateDimension(dims []*swarming.SwarmingRpcsStringListPair) fleet.DutState {
	for _, p := range dims {
		if p.Key != DutStateDimensionKey {
			continue
		}
		if len(p.Value) != 1 {
			return fleet.DutState_DutStateInvalid
		}
		return dutStateMap[p.Value[0]]
	}
	return fleet.DutState_DutStateInvalid
}

// dutStateMap maps string values to DutState values.  The zero value
// for unknown keys is DutState_StateInvalid.
var dutStateMap = map[string]fleet.DutState{
	"ready":         fleet.DutState_Ready,
	"needs_cleanup": fleet.DutState_NeedsCleanup,
	"needs_repair":  fleet.DutState_NeedsRepair,
	"needs_reset":   fleet.DutState_NeedsReset,
	"repair_failed": fleet.DutState_RepairFailed,
}
