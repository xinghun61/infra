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

// SwarmingClient exposes Swarming client API used by this package.
// In prod, a SwarmingClient for interacting with the Swarming service will be used.
// Tests should use a fake.
type SwarmingClient interface {
	ListAliveBotsInPool(context.Context, string, strpair.Map) ([]*swarming.SwarmingRpcsBotInfo, error)
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
	dims.Set("pool", pool)
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
