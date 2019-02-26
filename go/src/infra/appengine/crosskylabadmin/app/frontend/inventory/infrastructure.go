// Copyright 2019 The LUCI Authors.
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
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
	"math/rand"
	"sort"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	// Number of drones least loaded drones to consider when picking a drone for a DUT.
	//
	// A random drone from these is assigned to the DUT.
	leastLoadedDronesCount = 8
)

// AssignDutsToDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) AssignDutsToDrones(ctx context.Context, req *fleet.AssignDutsToDronesRequest) (resp *fleet.AssignDutsToDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}

	f := func() error {
		if err := s.Refresh(ctx); err != nil {
			return err
		}

		hostnameToID := mapHostnameToDUTs(s.Lab.GetDuts())
		assigned := make([]*fleet.AssignDutsToDronesResponse_Item, 0, len(req.Assignments))
		for _, a := range req.Assignments {
			id := a.DutId
			if a.DutHostname != "" {
				d, ok := hostnameToID[a.DutHostname]
				if !ok {
					return errors.Reason("assign duts to drone: Unknown DUT hostname %s", a.DutHostname).Err()
				}
				id = d.GetCommon().GetId()
			}

			dh := a.GetDroneHostname()
			if dh == "" {
				dh = pickDroneForDUT(ctx, s.Infrastructure)
				logging.Debugf(ctx, "Picked drone %s for DUT %s", dh, a.DutId)
			}
			if err = assignDutToDrone(ctx, s.Infrastructure, id, dh); err != nil {
				return err
			}
			assigned = append(assigned, &fleet.AssignDutsToDronesResponse_Item{
				DroneHostname: dh,
				DutId:         id,
			})
		}
		url, err := s.Commit(ctx, "assign DUTs")
		if err != nil {
			return err
		}
		resp = &fleet.AssignDutsToDronesResponse{
			Assigned: assigned,
			Url:      url,
		}
		return nil
	}
	if err = retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "assignDutsToDronesNoRetry")); err != nil {
		return nil, err
	}
	return resp, nil
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

// assignDutToDrone upates infra to assign the DUT with given ID to the drone with given hostname.
func assignDutToDrone(ctx context.Context, infra *inventory.Infrastructure, dutID string, hostname string) error {
	env := config.Get(ctx).Inventory.Environment
	servers := infra.GetServers()
	if server, ok := findDutServer(servers, dutID); ok {
		return status.Errorf(
			codes.InvalidArgument,
			"dut %s is already assigned to drone %s in environment %s",
			dutID, server.GetHostname(), server.GetEnvironment(),
		)
	}

	server, ok := findNamedServer(servers, hostname)
	if !ok {
		return status.Error(codes.NotFound, fmt.Sprintf("drone %s does not exist", hostname))
	}
	if server.GetEnvironment().String() != env {
		return status.Errorf(
			codes.InvalidArgument,
			"drone %s is in environment %s instead of %s",
			server.GetHostname(), server.GetEnvironment().String(), env,
		)
	}
	server.DutUids = append(server.DutUids, dutID)
	return nil
}

// pickDroneForDUT returns hostname of a drone to use for the DUT with the given ID.
//
// Returns "" if no drone can be found.
func pickDroneForDUT(ctx context.Context, infra *inventory.Infrastructure) string {
	ds := filterSkylabDronesInEnvironment(ctx, infra.GetServers())
	// ds is a new slice. Sorting it does not modify infra.
	sortDronesByAscendingDUTCount(ds)

	dc := minInt(leastLoadedDronesCount, len(ds))
	ds = ds[:dc]
	if len(ds) == 0 {
		return ""
	}
	return ds[rand.Intn(len(ds))].GetHostname()
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

	hostnameToID := mapHostnameToDUTs(store.Lab.GetDuts())
	for _, removal := range req.Removals {
		id := removal.DutId
		if removal.DutHostname != "" {
			d, ok := hostnameToID[removal.DutHostname]
			if !ok {
				return nil, errors.Reason("remove duts to drone: Unknown DUT hostname %s", removal.DutHostname).Err()
			}
			id = d.GetCommon().GetId()
		}

		serverToRemove := removal.DroneHostname

		var ok bool
		var server *inventory.Server
		if serverToRemove == "" {
			server, ok = findDutServer(store.Infrastructure.GetServers(), id)
		} else {
			server, ok = findNamedServer(store.Infrastructure.GetServers(), id)
		}
		if !ok {
			continue
		}
		if server.GetEnvironment().String() != env {
			continue
		}

		if !removeDutFromServer(server, id) {
			continue
		}

		resp.Removed = append(resp.Removed,
			&fleet.RemoveDutsFromDronesResponse_Item{
				DutId:         id,
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

// filterSkylabDronesInEnvironment returns drones in the current environment
// from a list of servers
func filterSkylabDronesInEnvironment(ctx context.Context, servers []*inventory.Server) []*inventory.Server {
	env := config.Get(ctx).Inventory.Environment
	ds := make([]*inventory.Server, 0, len(servers))
	for _, s := range servers {
		if s.GetEnvironment().String() != env {
			continue
		}
		for _, r := range s.GetRoles() {
			if r == inventory.Server_ROLE_SKYLAB_DRONE {
				ds = append(ds, s)
				break
			}
		}
	}
	return ds
}

func sortDronesByAscendingDUTCount(ds []*inventory.Server) {
	sort.SliceStable(ds, func(i, j int) bool {
		return len(ds[i].DutUids) < len(ds[j].DutUids)
	})
}

func mapHostnameToDUTs(duts []*inventory.DeviceUnderTest) map[string]*inventory.DeviceUnderTest {
	m := make(map[string]*inventory.DeviceUnderTest)
	for _, d := range duts {
		m[d.GetCommon().GetHostname()] = d
	}
	return m
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

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
