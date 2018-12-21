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

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
)

// GerritFactory is a contsructor for a GerritClient
type GerritFactory func(c context.Context, host string) (gerrit.GerritClient, error)

// GitilesFactory is a contsructor for a GerritClient
type GitilesFactory func(c context.Context, host string) (gitiles.GitilesClient, error)

// TrackerFactory is a constructor for a TrackerServer object.
type TrackerFactory func() fleet.TrackerServer

// ServerImpl implements the fleet.InventoryServer interface.
type ServerImpl struct {
	// GerritFactory is an optional factory function for creating gerrit client.
	//
	// If GerritFactory is nil, clients.NewGerritClient is used.
	GerritFactory GerritFactory

	// GitilesFactory is an optional factory function for creating gitiles client.
	//
	// If GitilesFactory is nil, clients.NewGitilesClient is used.
	GitilesFactory GitilesFactory

	// TrackerServerFactory is a required factory function for creating a tracker object.
	//
	// TODO(pprabhu) Move tracker/tasker to individual sub-packages and inject
	// dependencies directly (instead of factory functions).
	TrackerFactory TrackerFactory
}

func (is *ServerImpl) newGerritClient(c context.Context, host string) (gerrit.GerritClient, error) {
	if is.GerritFactory != nil {
		return is.GerritFactory(c, host)
	}
	return clients.NewGerritClient(c, host)
}

func (is *ServerImpl) newGitilesClient(c context.Context, host string) (gitiles.GitilesClient, error) {
	if is.GitilesFactory != nil {
		return is.GitilesFactory(c, host)
	}
	return clients.NewGitilesClient(c, host)
}

// EnsurePoolHealthy implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) EnsurePoolHealthy(ctx context.Context, req *fleet.EnsurePoolHealthyRequest) (resp *fleet.EnsurePoolHealthyResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	inventoryConfig := config.Get(ctx).Inventory

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	lab, err := is.fetchLabInventory(ctx, inventoryConfig)
	if err != nil {
		return nil, err
	}

	duts := selectDutsFromInventory(lab, req.DutSelector, inventoryConfig.Environment)
	if len(duts) == 0 {
		// Technically correct: No DUTs were selected so both target and spare are
		// empty and healthy and no changes were required.
		return &fleet.EnsurePoolHealthyResponse{}, nil
	}

	pb, err := is.initializedPoolBalancer(ctx, req, duts)
	if err != nil {
		return nil, err
	}
	logging.Debugf(ctx, "Pool balancer initial state: %+v", pb)

	changes, failures := pb.EnsureTargetHealthy(int(req.MaxUnhealthyDuts))
	ret := &fleet.EnsurePoolHealthyResponse{
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
	}

	if !req.GetOptions().GetDryrun() {
		u, err := is.commitChanges(ctx, inventoryConfig, lab, changes)
		if err != nil {
			return nil, err
		}
		ret.Url = u
	}
	return ret, nil
}

// ResizePool implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) ResizePool(ctx context.Context, req *fleet.ResizePoolRequest) (resp *fleet.ResizePoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	inventoryConfig := config.Get(ctx).Inventory

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	lab, err := is.fetchLabInventory(ctx, inventoryConfig)
	if err != nil {
		return nil, err
	}
	duts := selectDutsFromInventory(lab, req.DutSelector, inventoryConfig.Environment)
	changes, err := resizePool(duts, req.TargetPool, int(req.TargetPoolSize), req.SparePool)
	if err != nil {
		return nil, err
	}
	u, err := is.commitChanges(ctx, inventoryConfig, lab, changes)
	if err != nil {
		return nil, err
	}
	return &fleet.ResizePoolResponse{
		Url:     u,
		Changes: changes,
	}, nil
}

func selectDutsFromInventory(lab *inventory.Lab, sel *fleet.DutSelector, env string) []*inventory.DeviceUnderTest {
	m := sel.GetModel()
	duts := []*inventory.DeviceUnderTest{}
	for _, d := range lab.Duts {
		if d.GetCommon().GetEnvironment().String() == env && d.GetCommon().GetLabels().GetModel() == m {
			duts = append(duts, d)
		}
	}
	return duts
}

func (is *ServerImpl) fetchLabInventory(ctx context.Context, inventoryConfig *config.Inventory) (*inventory.Lab, error) {
	gc, err := is.newGitilesClient(ctx, inventoryConfig.GitilesHost)
	if err != nil {
		return nil, errors.Annotate(err, "create gitiles client").Err()
	}
	return fetchLabInventory(ctx, gc)
}

func (is *ServerImpl) initializedPoolBalancer(ctx context.Context, req *fleet.EnsurePoolHealthyRequest, duts []*inventory.DeviceUnderTest) (*poolBalancer, error) {
	pb, err := newPoolBalancer(duts, req.TargetPool, req.SparePool)
	if err != nil {
		return nil, err
	}
	if err := setDutHealths(ctx, is.TrackerFactory(), pb); err != nil {
		return nil, err
	}
	return pb, err
}

func (is *ServerImpl) commitChanges(ctx context.Context, inventoryConfig *config.Inventory, lab *inventory.Lab, changes []*fleet.PoolChange) (string, error) {
	if len(changes) == 0 {
		// No inventory changes are required.
		// TODO(pprabhu) add a unittest enforcing this.
		return "", nil
	}

	if err := applyChanges(lab, changes); err != nil {
		return "", errors.Annotate(err, "apply balance pool changes").Err()
	}
	gerritC, err := is.newGerritClient(ctx, inventoryConfig.GerritHost)
	if err != nil {
		return "", errors.Annotate(err, "create gerrit client").Err()
	}
	return commitInventory(ctx, gerritC, lab)
}

func applyChanges(lab *inventory.Lab, changes []*fleet.PoolChange) error {
	oldPool := make(map[string]inventory.SchedulableLabels_DUTPool)
	newPool := make(map[string]inventory.SchedulableLabels_DUTPool)
	for _, c := range changes {
		oldPool[c.DutId] = inventory.SchedulableLabels_DUTPool(inventory.SchedulableLabels_DUTPool_value[c.OldPool])
		newPool[c.DutId] = inventory.SchedulableLabels_DUTPool(inventory.SchedulableLabels_DUTPool_value[c.NewPool])
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

// RemoveDutsFromDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) RemoveDutsFromDrones(ctx context.Context, req *fleet.RemoveDutsFromDronesRequest) (resp *fleet.RemoveDutsFromDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Error(codes.Unimplemented, "")
}

// AssignDutsToDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) AssignDutsToDrones(ctx context.Context, req *fleet.AssignDutsToDronesRequest) (resp *fleet.AssignDutsToDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Error(codes.Unimplemented, "")
}
