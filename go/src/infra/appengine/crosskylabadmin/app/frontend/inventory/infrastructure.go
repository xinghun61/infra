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

// AssignDutsToDrones implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) AssignDutsToDrones(ctx context.Context, req *fleet.AssignDutsToDronesRequest) (resp *fleet.AssignDutsToDronesResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
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
		c := newGlobalInvCache(ctx, s)
		assigned := make([]*fleet.AssignDutsToDronesResponse_Item, 0, len(req.Assignments))
		for _, a := range req.Assignments {
			var dutID string
			switch {
			case a.DutHostname != "":
				var ok bool
				dutID, ok = c.hostnameToID[a.DutHostname]
				if !ok {
					return status.Errorf(codes.NotFound, "unknown DUT hostname %s", a.DutHostname)
				}
			case a.DutId != "":
				dutID = a.DutId
			default:
				return status.Errorf(codes.InvalidArgument, "must supply one of DUT hostname or ID")
			}
			d, err := assignDUT(ctx, c, dutID)
			if err != nil {
				return err
			}
			assigned = append(assigned, &fleet.AssignDutsToDronesResponse_Item{
				DroneHostname: d,
				DutId:         dutID,
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

// globalInvCache wraps an InventoryStore and keeps various lookup caches.
// Unlike invCache, this ignores the environment and includes the entire inventory.
type globalInvCache struct {
	store           *gitstore.InventoryStore
	hostnameToID    map[string]string
	droneForDUT     map[string]*inventory.Server
	idToDUT         map[string]*inventory.DeviceUnderTest
	hostnameToDrone map[string]*inventory.Server
}

func newGlobalInvCache(ctx context.Context, s *gitstore.InventoryStore) *globalInvCache {
	ic := globalInvCache{
		store:           s,
		hostnameToID:    make(map[string]string),
		droneForDUT:     make(map[string]*inventory.Server),
		idToDUT:         make(map[string]*inventory.DeviceUnderTest),
		hostnameToDrone: make(map[string]*inventory.Server),
	}
	for _, d := range s.Lab.GetDuts() {
		c := d.GetCommon()
		ic.hostnameToID[c.GetHostname()] = c.GetId()
		ic.idToDUT[c.GetId()] = d
	}
	for _, srv := range s.Infrastructure.GetServers() {
		if !isDrone(srv) {
			continue
		}
		ic.hostnameToDrone[srv.GetHostname()] = srv
		for _, d := range srv.DutUids {
			ic.droneForDUT[d] = srv
		}
	}
	return &ic
}

// assignDUT assigns the given DUT to the queen drone in the current environment.
func assignDUT(ctx context.Context, c *globalInvCache, dutID string) (drone string, _ error) {
	cfg := config.Get(ctx).Inventory
	d := queenDroneName(cfg.Environment)
	logging.Debugf(ctx, "Using pseudo-drone %s for DUT %s", d, dutID)
	if _, ok := c.idToDUT[dutID]; !ok {
		return "", status.Error(codes.NotFound, fmt.Sprintf("DUT %s does not exist", dutID))
	}
	if server, ok := c.droneForDUT[dutID]; ok {
		return "", status.Errorf(codes.InvalidArgument,
			"dut %s is already assigned to drone %s", dutID, server.GetHostname())
	}
	server, ok := c.hostnameToDrone[d]
	if !ok {
		panic(fmt.Sprintf("drone %s does not exist", d))
	}
	server.DutUids = append(server.DutUids, dutID)
	c.droneForDUT[dutID] = server
	c.idToDUT[dutID].RemovalReason = nil
	return d, nil
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
		i, err := dr.removeDUT(ctx, r)
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

// dutRemover wraps an InventoryStore and implements removing DUTs
// from drones.  This struct contains various internal lookup caches.
type dutRemover struct {
	*globalInvCache
}

func newDUTRemover(ctx context.Context, s *gitstore.InventoryStore) *dutRemover {
	return &dutRemover{
		globalInvCache: newGlobalInvCache(ctx, s),
	}
}

// removeDUT removes a DUT per a DUT removal request and returns a response.
func (dr *dutRemover) removeDUT(ctx context.Context, r *fleet.RemoveDutsFromDronesRequest_Item) (*fleet.RemoveDutsFromDronesResponse_Item, error) {
	rr, err := dr.unpackRequest(r)
	if err != nil {
		return nil, err
	}
	srv, ok := dr.droneForDUT[rr.dutID]
	if !ok {
		return nil, nil
	}
	cfg := config.Get(ctx).Inventory
	isQueenDrone := srv.GetHostname() == queenDroneName(cfg.Environment)
	if !isQueenDrone && srv.GetEnvironment().String() != cfg.Environment {
		return nil, nil
	}
	srv.DutUids = removeSliceString(srv.DutUids, rr.dutID)
	delete(dr.droneForDUT, rr.dutID)
	dr.idToDUT[rr.dutID].RemovalReason = rr.reason
	return &fleet.RemoveDutsFromDronesResponse_Item{
		DutId:         rr.dutID,
		DroneHostname: srv.GetHostname(),
	}, nil
}

// removeRequest is an unpacked fleet.RemoveDutsFromDronesRequest_Item.
type removeRequest struct {
	dutID  string
	reason *inventory.RemovalReason
}

func (dr *dutRemover) unpackRequest(r *fleet.RemoveDutsFromDronesRequest_Item) (removeRequest, error) {
	var rr removeRequest
	if err := dr.unpackRequestDUTID(r, &rr); err != nil {
		return rr, err
	}
	var err error
	rr.reason, err = unpackRemovalReason(r)
	if err != nil {
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

func unpackRemovalReason(r *fleet.RemoveDutsFromDronesRequest_Item) (*inventory.RemovalReason, error) {
	enc := r.GetRemovalReason()
	if len(enc) == 0 {
		return nil, nil
	}
	var rr inventory.RemovalReason
	if err := proto.Unmarshal(enc, &rr); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid RemovalReason")
	}
	return &rr, nil
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
