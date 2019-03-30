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
	"math/rand"
	"sort"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"

	"github.com/golang/protobuf/proto"
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
			i, err := assignDutToDrone(ctx, s.Infrastructure, hostnameToID, a)
			if err != nil {
				return err
			}
			assigned = append(assigned, i)
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
	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	f := func() error {
		if err := s.Refresh(ctx); err != nil {
			return err
		}
		var err error
		resp, err = removeDutsFromDrones(ctx, s, req)
		if err != nil {
			return err
		}
		if err := commitRemoveDuts(ctx, s, resp); err != nil {
			return err
		}
		return nil
	}
	err = retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "removeDutsFromDronesNoRetry"))
	return resp, err
}

func assignDutToDrone(ctx context.Context, infra *inventory.Infrastructure, hostnameToID map[string]*inventory.DeviceUnderTest, a *fleet.AssignDutsToDronesRequest_Item) (*fleet.AssignDutsToDronesResponse_Item, error) {
	env := config.Get(ctx).Inventory.Environment
	id := a.DutId
	if a.DutHostname != "" {
		d, ok := hostnameToID[a.DutHostname]
		if !ok {
			return nil, status.Errorf(codes.NotFound, "unknown DUT hostname %s", a.DutHostname)
		}
		id = d.GetCommon().GetId()
	}

	dh := a.GetDroneHostname()
	if dh == "" {
		dh = pickDroneForDUT(ctx, infra)
		logging.Debugf(ctx, "Picked drone %s for DUT %s", dh, a.DutId)
	}

	servers := infra.GetServers()
	if server, ok := findDutServer(servers, id); ok {
		return nil, status.Errorf(
			codes.InvalidArgument,
			"dut %s is already assigned to drone %s in environment %s",
			id, server.GetHostname(), server.GetEnvironment(),
		)
	}

	server, ok := findNamedServer(servers, dh)
	if !ok {
		return nil, status.Error(codes.NotFound, fmt.Sprintf("drone %s does not exist", dh))
	}
	if server.GetEnvironment().String() != env {
		return nil, status.Errorf(
			codes.InvalidArgument,
			"drone %s is in environment %s instead of %s",
			dh, server.GetEnvironment().String(), env,
		)
	}
	server.DutUids = append(server.DutUids, id)

	return &fleet.AssignDutsToDronesResponse_Item{
		DroneHostname: dh,
		DutId:         id,
	}, nil
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

// commitRemoveDuts commits an in-progress response returned from
// removeDutsFromDrones.
func commitRemoveDuts(ctx context.Context, s *gitstore.InventoryStore, resp *fleet.RemoveDutsFromDronesResponse) error {
	if len(resp.Removed) == 0 {
		return nil
	}
	var err error
	resp.Url, err = s.Commit(ctx, "remove DUTs")
	return err
}

// removeDutsFromDrones implements removing DUTs from drones on an
// InventoryStore.  This is called within a load/commit/retry context.
func removeDutsFromDrones(ctx context.Context, s *gitstore.InventoryStore, req *fleet.RemoveDutsFromDronesRequest) (*fleet.RemoveDutsFromDronesResponse, error) {
	removed := make([]*fleet.RemoveDutsFromDronesResponse_Item, 0, len(req.Removals))
	dr := newDUTRemover(ctx, s)
	for _, r := range req.Removals {
		i, err := dr.removeDut(ctx, r)
		if err != nil {
			return nil, err
		}
		if i == nil {
			// DUT did not belong to any drone.
			continue
		}
		removed = append(removed, i)
	}
	return &fleet.RemoveDutsFromDronesResponse{
		Removed: removed,
	}, nil
}

type dutRemover struct {
	store        *gitstore.InventoryStore
	hostnameToID map[string]string
	droneForDUT  map[string]*inventory.Server
}

func newDUTRemover(ctx context.Context, s *gitstore.InventoryStore) *dutRemover {
	env := config.Get(ctx).Inventory.Environment
	dr := dutRemover{
		store:        s,
		hostnameToID: make(map[string]string),
		droneForDUT:  make(map[string]*inventory.Server),
	}
	for _, d := range s.Lab.GetDuts() {
		c := d.GetCommon()
		dr.hostnameToID[c.GetHostname()] = c.GetId()
	}
	for _, srv := range s.Infrastructure.GetServers() {
		if srv.GetEnvironment().String() != env {
			continue
		}
		// TODO(ayatane): We should filter on server role for Skylab
		// drones, but only Skylab drones have DUTs right now.
		for _, d := range srv.DutUids {
			dr.droneForDUT[d] = srv
		}
	}
	return &dr
}

func (dr *dutRemover) removeDut(ctx context.Context, r *fleet.RemoveDutsFromDronesRequest_Item) (*fleet.RemoveDutsFromDronesResponse_Item, error) {
	rr, err := dr.unpackRequest(r)
	if err != nil {
		return nil, err
	}
	srv, ok := dr.droneForDUT[rr.dutID]
	if !ok {
		if rr.drone != "" {
			return nil, status.Errorf(codes.FailedPrecondition, "DUT %s is not assigned to a drone", rr.dutID)
		}
		return nil, nil
	}
	if rr.drone != "" && rr.drone != srv.GetHostname() {
		return nil, status.Errorf(codes.FailedPrecondition, "DUT %s is not on drone %s", rr.dutID, rr.drone)
	}
	srv.DutUids = removeSliceString(srv.DutUids, rr.dutID)
	delete(dr.droneForDUT, rr.dutID)
	return &fleet.RemoveDutsFromDronesResponse_Item{
		DutId:         rr.dutID,
		DroneHostname: srv.GetHostname(),
	}, nil
}

// removeRequest is an unpacked fleet.RemoveDutsFromDronesRequest_Item.
type removeRequest struct {
	dutID  string
	drone  string
	reason *inventory.RemovalReason
}

func (dr *dutRemover) unpackRequest(r *fleet.RemoveDutsFromDronesRequest_Item) (removeRequest, error) {
	rr := removeRequest{
		drone: r.DroneHostname,
	}
	if err := dr.unpackRequestDUTID(r, &rr); err != nil {
		return rr, err
	}
	if err := dr.unpackRequestReason(r, &rr); err != nil {
		return rr, err
	}
	return rr, nil
}

func (dr *dutRemover) unpackRequestDUTID(r *fleet.RemoveDutsFromDronesRequest_Item, rr *removeRequest) error {
	switch {
	case r.DutHostname != "":
		var ok bool
		rr.dutID, ok = dr.hostnameToID[r.DutHostname]
		if !ok {
			return status.Errorf(codes.NotFound, "unknown DUT hostname %s", r.DutHostname)
		}
	case r.DutId != "":
		rr.dutID = r.DutId
	default:
		return status.Errorf(codes.InvalidArgument, "must supply one of DUT hostname or ID")
	}
	return nil
}

func (dr *dutRemover) unpackRequestReason(r *fleet.RemoveDutsFromDronesRequest_Item, rr *removeRequest) error {
	enc := r.GetRemovalReason()
	if len(enc) == 0 {
		return nil
	}
	rr.reason = new(inventory.RemovalReason)
	if err := proto.Unmarshal(enc, rr.reason); err != nil {
		return status.Errorf(codes.InvalidArgument, "invalid RemovalReason")
	}
	return nil
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

func removeSliceString(sl []string, s string) []string {
	for i, v := range sl {
		if v != s {
			continue
		}
		copy(sl[i:], sl[i+1:])
		return sl[:len(sl)-1]
	}
	return sl
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
