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

// Package inventory implements the fleet.Inventory service end-points of
// corsskylabadmin.
package inventory

import (
	"fmt"
	"time"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/inventory/internal/store"
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

var transientErrorRetriesTemplate = retry.ExponentialBackoff{
	Limited: retry.Limited{
		Delay: 200 * time.Millisecond,
		// Don't retry too often, leaving some headroom for clients to retry if they wish.
		Retries: 3,
	},
	// Slow down quickly so as to not flood outbound requests on retries.
	Multiplier: 4,
	MaxDelay:   5 * time.Second,
}

// transientErrorRetries returns a retry.Factory to use on transient errors on
// outbound requests.
func transientErrorRetries() retry.Factory {
	next := func() retry.Iterator {
		it := transientErrorRetriesTemplate
		return &it
	}
	return transient.Only(next)
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

func (is *ServerImpl) newStore(ctx context.Context) (*store.GitStore, error) {
	inventoryConfig := config.Get(ctx).Inventory
	gerritC, err := is.newGerritClient(ctx, inventoryConfig.GerritHost)
	if err != nil {
		return nil, errors.Annotate(err, "create git store").Err()
	}
	gitilesC, err := is.newGitilesClient(ctx, inventoryConfig.GitilesHost)
	if err != nil {
		return nil, errors.Annotate(err, "create git store").Err()
	}
	return store.NewGitStore(gerritC, gitilesC), nil
}

// RemoveDutsFromDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) RemoveDutsFromDrones(ctx context.Context, req *fleet.RemoveDutsFromDronesRequest) (resp *fleet.RemoveDutsFromDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	err = retry.Retry(
		ctx,
		transientErrorRetries(),
		func() error {
			var ierr error
			resp, ierr = is.removeDutsFromDronesNoRetry(ctx, req)
			return ierr
		},
		retry.LogCallback(ctx, "removeDutsFromDronesNoRetry"),
	)
	return resp, err
}

func (is *ServerImpl) removeDutsFromDronesNoRetry(ctx context.Context, req *fleet.RemoveDutsFromDronesRequest) (*fleet.RemoveDutsFromDronesResponse, error) {
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err := store.Refresh(ctx); err != nil {
		return nil, err
	}

	resp := &fleet.RemoveDutsFromDronesResponse{
		Removed: make([]*fleet.RemoveDutsFromDronesResponse_Item, 0, len(req.Removals)),
	}

	env := config.Get(ctx).Inventory.Environment

	for _, removal := range req.Removals {
		serverToRemove := removal.DroneHostname

		var ok bool
		var server *inventory.Server
		if serverToRemove == "" {
			server, ok = findDutServer(store.Infrastructure.GetServers(), removal.DutId)
		} else {
			server, ok = findNamedServer(store.Infrastructure.GetServers(), removal.DutId)
		}
		if !ok {
			continue
		}
		if server.GetEnvironment().String() != env {
			continue
		}

		if !removeDutFromServer(server, removal.DutId) {
			continue
		}

		resp.Removed = append(resp.Removed,
			&fleet.RemoveDutsFromDronesResponse_Item{
				DutId:         removal.DutId,
				DroneHostname: server.GetHostname(),
			})
	}

	if len(resp.Removed) == 0 {
		return resp, nil
	}

	if resp.Url, err = store.Commit(ctx, "remove DUTs"); err != nil {
		return nil, err
	}

	return resp, nil
}

// findNamedServer finds the server with the given hostname.
//
// Servers should each have unique hostnames; this function only returns the first matching occurrence.
func findNamedServer(servers []*inventory.Server, hostname string) (server *inventory.Server, ok bool) {
	for _, server := range servers {
		if hostname == server.GetHostname() {
			return server, true
		}
	}
	return nil, false
}

// findDutServer finds the server that the given Dut is on, if it exists.
//
// Duts should only be assigned to a single server; this function only returns the first server
// occurrence.
func findDutServer(servers []*inventory.Server, dutID string) (server *inventory.Server, ok bool) {
	for _, server := range servers {
		for _, dut := range server.DutUids {
			if dut == dutID {
				return server, true
			}
		}
	}
	return nil, false
}

// removeDutFromServer removes the given Dut from the given server, if it exists.
//
// Duts should only occur once on a server; this function only removes the first occurrence.
func removeDutFromServer(server *inventory.Server, dutID string) (ok bool) {
	for index, dut := range server.DutUids {
		if dut == dutID {
			server.DutUids = append(server.DutUids[:index], server.DutUids[index+1:]...)
			return true
		}
	}
	return false
}

// AssignDutsToDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) AssignDutsToDrones(ctx context.Context, req *fleet.AssignDutsToDronesRequest) (resp *fleet.AssignDutsToDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	err = retry.Retry(
		ctx,
		transientErrorRetries(),
		func() error {
			var ierr error
			resp, ierr = is.assignDutsToDronesNoRetry(ctx, req)
			return ierr
		},
		retry.LogCallback(ctx, "assignDutsToDronesNoRetry"),
	)
	return resp, err
}

func (is *ServerImpl) assignDutsToDronesNoRetry(ctx context.Context, req *fleet.AssignDutsToDronesRequest) (*fleet.AssignDutsToDronesResponse, error) {
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err := store.Refresh(ctx); err != nil {
		return nil, err
	}

	resp := &fleet.AssignDutsToDronesResponse{
		Assigned: make([]*fleet.AssignDutsToDronesResponse_Item, 0, len(req.Assignments)),
	}

	env := config.Get(ctx).Inventory.Environment

	for _, assignment := range req.Assignments {
		dutToAssign := assignment.DutId
		serverToAssign := assignment.DroneHostname
		if server, ok := findDutServer(store.Infrastructure.GetServers(), dutToAssign); ok {
			return nil, status.Errorf(codes.InvalidArgument,
				"dut %s is already assigned to drone %s in environment %s",
				dutToAssign, server.GetHostname(), server.GetEnvironment())
		}

		server, ok := findNamedServer(store.Infrastructure.GetServers(), serverToAssign)
		if !ok {
			return nil, status.Error(codes.NotFound,
				fmt.Sprintf("drone %s does not exist", serverToAssign))
		}
		if server.GetEnvironment().String() != env {
			return nil, status.Errorf(codes.InvalidArgument,
				"drone %s is in environment %s instead of %s",
				server.GetHostname(), server.GetEnvironment().String(), env)
		}

		server.DutUids = append(server.DutUids, dutToAssign)
		resp.Assigned = append(resp.Assigned,
			&fleet.AssignDutsToDronesResponse_Item{
				DroneHostname: serverToAssign,
				DutId:         dutToAssign,
			})
	}

	if resp.Url, err = store.Commit(ctx, "assign DUTs"); err != nil {
		return nil, err
	}

	return resp, nil
}
