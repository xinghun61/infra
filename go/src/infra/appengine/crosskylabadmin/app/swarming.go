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
	"net/http"
	"time"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
)

const (
	// maxConcurrentSwarmingCalls is the maximum number of concurrent swarming calls
	// made within the context of a single RPC call to this app.
	//
	// There is no per-instance limit (yet).
	maxConcurrentSwarmingCalls = 10

	// dutIDDimensionKey identifies the swarming dimension containing the ID for
	// the DUT corresponding to a bot.
	dutIDDimensionKey = "dut_id"
	// dutStateDimensionKey identifies the swarming dimension containing the
	// autotest DUT state for a bot.
	dutStateDimensionKey = "dut_state"
	// poolDimensionKey identifies the swarming pool dimension.
	poolDimensionKey = "pool"
)

// SwarmingClient exposes Swarming client API used by this package.
//
// In prod, a SwarmingClient for interacting with the Swarming service will be used.
// Tests should use a fake.
type SwarmingClient interface {
	ListAliveBotsInPool(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error)
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

// swarmingClientFactory implements a single method to obtain a SwarmingClient instance.
type swarmingClientFactory struct {
	// swarmingClientHook provides a way to override the swarming client bindings.
	// Tests should override swarmingClientHook to return a fake SwarmingClient.
	// If nil, a real SwarmingClient will be used.
	swarmingClientHook func(c context.Context, host string) (SwarmingClient, error)
}

// swarmingClient creats a SwarmingClient. All trackerServerImpl methods should
// use swarmingClient to obtain a SwarmingClient.
func (tsi *swarmingClientFactory) swarmingClient(c context.Context, host string) (SwarmingClient, error) {
	if tsi.swarmingClientHook != nil {
		return tsi.swarmingClientHook(c, host)
	}
	return NewSwarmingClient(c, host)
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
// Use dims to restrict to dimensions beyond pool.
func (sc *swarmingClientImpl) ListAliveBotsInPool(c context.Context, pool string, dims strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error) {
	bis := []*swarming.SwarmingRpcsBotInfo{}
	dims.Set(poolDimensionKey, pool)
	call := sc.Bots.List().Dimensions(dims.Format()...).IsDead("FALSE")
	for {
		ic, _ := context.WithTimeout(c, 60*time.Second)
		response, err := call.Context(ic).Do()
		if err != nil {
			return nil, errors.Annotate(err, "failed to list alive bots in pool %s", pool).Err()
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
			Key:   dutIDDimensionKey,
			Value: args.DutID,
		},
		{
			Key:   poolDimensionKey,
			Value: args.Pool,
		},
	}
	if args.DutState != "" {
		dims = append(dims, &swarming.SwarmingRpcsStringPair{
			Key:   dutStateDimensionKey,
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
		return "", err
	}
	return resp.TaskId, nil
}
