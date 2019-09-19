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

package inventory

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/dutpool"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/appengine/crosskylabadmin/app/frontend/internal/swarming"
	"infra/libs/skylab/inventory"
	"sync"

	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// BalancePools implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) BalancePools(ctx context.Context, req *fleet.BalancePoolsRequest) (resp *fleet.BalancePoolsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	err = retry.Retry(
		ctx,
		transientErrorRetries(),
		func() error {
			var ierr error
			resp, ierr = is.balancePoolsNoRetry(ctx, req)
			return ierr
		},
		retry.LogCallback(ctx, "BalancePools"),
	)
	return resp, err
}

func (is *ServerImpl) balancePoolsNoRetry(ctx context.Context, req *fleet.BalancePoolsRequest) (*fleet.BalancePoolsResponse, error) {
	cfg := config.Get(ctx)
	sc, err := is.newSwarmingClient(ctx, cfg.Swarming.Host)
	if err != nil {
		return nil, err
	}

	botsHealth, err := getBotsHealth(ctx, sc)
	if err != nil {
		return nil, err
	}

	inventoryConfig := config.Get(ctx).Inventory
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err = store.Refresh(ctx); err != nil {
		return nil, err
	}

	duts := selectDutsFromInventory(store.Lab, req.DutSelector, inventoryConfig.Environment)
	if len(duts) == 0 {
		// Technically correct: No DUTs were selected so both target and spare are
		// empty and healthy and no changes were required.
		logging.Infof(ctx, "no duts were found based on %s", req.DutSelector.String())
		return &fleet.BalancePoolsResponse{}, nil
	}

	mds := mapModelsToDUTs(duts, inventoryConfig.Environment)
	resp := &fleet.BalancePoolsResponse{
		ModelResult: make(map[string]*fleet.EnsurePoolHealthyResponse),
	}
	// Protects access to resp
	mResp := &sync.Mutex{}
	err = parallel.WorkPool(10, func(workC chan<- func() error) {
		for m, ds := range mds {
			// In-scope variables for goroutine closure.
			im := m
			ids := ds
			workC <- func() error {
				logging.Infof(ctx, "balancing pool for model: %s", m)
				iResp, err2 := ensurePoolHealthyForModel(ctx, ids, botsHealth, req.TargetPool, req.SparePool, req.MaxUnhealthyDuts)
				if err2 != nil {
					return err2
				}

				mResp.Lock()
				defer mResp.Unlock()
				resp.ModelResult[im] = iResp
				return nil
			}
		}
	})
	if err != nil {
		return nil, err
	}

	changes := collectChanges(resp.ModelResult)
	if !req.GetOptions().GetDryrun() {
		u, err := is.commitBalancePoolChanges(ctx, store, changes)
		if err != nil {
			return nil, err
		}
		resp.GeneratedChangeUrl = u
		for _, res := range resp.ModelResult {
			res.Url = u
		}
	}
	return resp, nil
}

// ResizePool implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) ResizePool(ctx context.Context, req *fleet.ResizePoolRequest) (resp *fleet.ResizePoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	if err = req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	err = retry.Retry(
		ctx,
		transientErrorRetries(),
		func() error {
			var ierr error
			resp, ierr = is.resizePoolNoRetry(ctx, req)
			return ierr
		},
		retry.LogCallback(ctx, "resizePoolNoRetry"),
	)
	return resp, err
}

func (is *ServerImpl) resizePoolNoRetry(ctx context.Context, req *fleet.ResizePoolRequest) (*fleet.ResizePoolResponse, error) {
	inventoryConfig := config.Get(ctx).Inventory
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err = store.Refresh(ctx); err != nil {
		return nil, err
	}

	duts := selectDutsFromInventory(store.Lab, req.DutSelector, inventoryConfig.Environment)
	changes, err := dutpool.Resize(duts, req.TargetPool, int(req.TargetPoolSize), req.SparePool)
	if err != nil {
		return nil, err
	}
	u, err := is.commitBalancePoolChanges(ctx, store, changes)
	if err != nil {
		return nil, err
	}
	return &fleet.ResizePoolResponse{
		Url:     u,
		Changes: changes,
	}, nil
}

func (is *ServerImpl) commitBalancePoolChanges(ctx context.Context, store *gitstore.InventoryStore, changes []*fleet.PoolChange) (string, error) {
	if len(changes) == 0 {
		// No inventory changes are required.
		// TODO(pprabhu) add a unittest enforcing this.
		return "", nil
	}
	if err := applyChanges(store.Lab, changes); err != nil {
		return "", errors.Annotate(err, "apply balance pool changes").Err()
	}
	return store.Commit(ctx, "balance pool")
}

func selectDutsFromInventory(lab *inventory.Lab, sel *fleet.DutSelector, env string) []*inventory.DeviceUnderTest {
	duts := []*inventory.DeviceUnderTest{}
	for _, d := range lab.Duts {
		if sel != nil && d.GetCommon().GetEnvironment().String() == env && dutMatchesSelector(d, sel) {
			duts = append(duts, d)
		}
		if sel == nil {
			duts = append(duts, d)
		}
	}
	return duts
}

func dutMatchesSelector(d *inventory.DeviceUnderTest, sel *fleet.DutSelector) bool {
	c := d.GetCommon()
	if sel.Id != "" && sel.Id != c.GetId() {
		return false
	}
	if sel.Hostname != "" && sel.Hostname != c.GetHostname() {
		return false
	}
	if sel.Model != "" && sel.Model != c.GetLabels().GetModel() {
		return false
	}
	return true
}

func ensurePoolHealthyForModel(ctx context.Context, duts []*inventory.DeviceUnderTest, botsHealth map[string]fleet.Health, target, spare string, maxUnhealthyDUTs int32) (*fleet.EnsurePoolHealthyResponse, error) {
	pb, err := dutpool.NewBalancer(duts, target, spare)
	if err != nil {
		return nil, errors.Annotate(err, "ensure pool healthy").Err()
	}
	pb.FillInHealth(botsHealth)
	logging.Debugf(ctx, "initial state: %+v", pb)

	changes, failures := pb.EnsureTargetHealthy(int(maxUnhealthyDUTs))
	return &fleet.EnsurePoolHealthyResponse{
		Failures: failures,
		TargetPoolStatus: &fleet.PoolStatus{
			Size:         int32(len(pb.Target)),
			HealthyCount: int32(pb.TargetHealthyCount()),
		},
		SparePoolStatus: &fleet.PoolStatus{
			Size:         int32(len(pb.Spare)),
			HealthyCount: int32(pb.SpareHealthyCount()),
		},
		Changes: changes,
	}, nil
}

func collectChanges(mrs map[string]*fleet.EnsurePoolHealthyResponse) []*fleet.PoolChange {
	// No way of knowning how many total changs are necessary without walking all
	// the changes.
	ret := make([]*fleet.PoolChange, 0)
	for _, res := range mrs {
		ret = append(ret, res.Changes...)
	}
	return ret
}

func applyChanges(lab *inventory.Lab, changes []*fleet.PoolChange) error {
	oldPool := make(map[string]inventory.SchedulableLabels_DUTPool)
	newPool := make(map[string]inventory.SchedulableLabels_DUTPool)
	for _, c := range changes {
		oldPool[c.DutId] = inventory.SchedulableLabels_DUTPool(inventory.SchedulableLabels_DUTPool_value[c.OldPool])
		np, ok := inventory.SchedulableLabels_DUTPool_value[c.NewPool]
		if !ok {
			// TODO: Add support for moving devices to non-critical pools.
			return fmt.Errorf("invalid destination pool %s, not a known critical pool", c.NewPool)
		}
		newPool[c.DutId] = inventory.SchedulableLabels_DUTPool(np)
	}

	for _, d := range lab.Duts {
		id := d.GetCommon().GetId()
		if np, ok := newPool[id]; ok {
			ls := d.GetCommon().GetLabels().GetCriticalPools()
			if ls == nil {
				return fmt.Errorf("critical pools missing for dut %s", id)
			}
			ls = removeOld(ls, oldPool[id])
			ls = append(ls, np)
			d.GetCommon().GetLabels().CriticalPools = ls
		}
	}
	return nil
}

func removeOld(ls []inventory.SchedulableLabels_DUTPool, old inventory.SchedulableLabels_DUTPool) []inventory.SchedulableLabels_DUTPool {
	for i, l := range ls {
		if l == old {
			copy(ls[i:], ls[i+1:])
			ls[len(ls)-1] = inventory.SchedulableLabels_DUT_POOL_INVALID
			return ls[:len(ls)-1]
		}
	}
	return ls
}

func mapModelsToDUTs(duts []*inventory.DeviceUnderTest, env string) map[string][]*inventory.DeviceUnderTest {
	dms := make(map[string][]*inventory.DeviceUnderTest)
	for _, d := range duts {
		if d.GetCommon().GetEnvironment().String() != env {
			continue
		}
		m := d.GetCommon().GetLabels().GetModel()
		dms[m] = append(dms[m], d)
	}
	return dms
}

func getBotsHealth(ctx context.Context, sc clients.SwarmingClient) (map[string]fleet.Health, error) {
	cfg := config.Get(ctx)
	bots, err := sc.ListAliveBotsInPool(ctx, cfg.Swarming.BotPool, strpair.Map{})
	if err != nil {
		return nil, err
	}
	botsHealth := make(map[string]fleet.Health, len(bots))
	for _, b := range bots {
		ds := clients.GetStateDimension(b.Dimensions)
		dims := swarming.DimensionsMap(b.Dimensions)
		dutID, err := swarming.ExtractSingleValuedDimension(dims, clients.DutIDDimensionKey)
		if err != nil {
			logging.Errorf(ctx, "fail to get dutID for bot %s: %s", b.BotId, err.Error())
			continue
		}
		if healthy := clients.HealthyDutStates[ds]; healthy {
			botsHealth[dutID] = fleet.Health_Healthy
		} else {
			botsHealth[dutID] = fleet.Health_Unhealthy
		}
	}
	return botsHealth, nil
}
