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
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/google"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/dronecfg"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/freeduts"
	dsinventory "infra/appengine/crosskylabadmin/app/frontend/internal/datastore/inventory"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"
)

// ListServers implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) ListServers(ctx context.Context, req *fleet.ListServersRequest) (resp *fleet.ListServersResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Error(codes.Unimplemented, "ListServers not yet implemented")
}

// GetDutInfo implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) GetDutInfo(ctx context.Context, req *fleet.GetDutInfoRequest) (resp *fleet.GetDutInfoResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	if err = req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	var dut *dsinventory.DeviceUnderTest
	if req.Id != "" {
		dut, err = dsinventory.GetSerializedDUTByID(ctx, req.Id)
	} else {
		dut, err = dsinventory.GetSerializedDUTByHostname(ctx, req.Hostname)
	}

	if err != nil {
		if datastore.IsErrNoSuchEntity(err) {
			return nil, status.Errorf(codes.NotFound, err.Error())
		}
		return nil, err
	}
	return &fleet.GetDutInfoResponse{
		Spec:    dut.Data,
		Updated: google.NewTimestamp(dut.Updated),
	}, nil
}

// GetDroneConfig implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) GetDroneConfig(ctx context.Context, req *fleet.GetDroneConfigRequest) (resp *fleet.GetDroneConfigResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	e, err := dronecfg.Get(ctx, req.Hostname)
	if err != nil {
		if datastore.IsErrNoSuchEntity(err) {
			return nil, status.Errorf(codes.NotFound, err.Error())
		}
		return nil, err
	}
	resp = &fleet.GetDroneConfigResponse{}
	for _, d := range e.DUTs {
		resp.Duts = append(resp.Duts, &fleet.GetDroneConfigResponse_Dut{
			Id:       d.ID,
			Hostname: d.Hostname,
		})
	}
	return resp, nil
}

// ListRemovedDuts implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) ListRemovedDuts(ctx context.Context, req *fleet.ListRemovedDutsRequest) (resp *fleet.ListRemovedDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	duts, err := freeduts.GetAll(ctx)
	if err != nil {
		return nil, err
	}
	resp = &fleet.ListRemovedDutsResponse{}
	for _, d := range duts {
		t, err := ptypes.TimestampProto(d.ExpireTime)
		if err != nil {
			return nil, err
		}
		resp.Duts = append(resp.Duts, &fleet.ListRemovedDutsResponse_Dut{
			Id:         d.ID,
			Hostname:   d.Hostname,
			Bug:        d.Bug,
			Comment:    d.Comment,
			ExpireTime: t,
			Model:      d.Model,
		})
	}
	return resp, nil
}

// UpdateCachedInventory implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) UpdateCachedInventory(ctx context.Context, req *fleet.UpdateCachedInventoryRequest) (resp *fleet.UpdateCachedInventoryResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err := store.Refresh(ctx); err != nil {
		return nil, err
	}
	duts := dutsInCurrentEnvironment(ctx, store.Lab.GetDuts())
	if err := dsinventory.UpdateDUTs(ctx, duts); err != nil {
		return nil, err
	}
	es := makeDroneConfigs(store.Infrastructure, store.Lab)
	if err := dronecfg.Update(ctx, es); err != nil {
		return nil, err
	}
	if err := updateFreeDUTs(ctx, store); err != nil {
		return nil, err
	}
	return &fleet.UpdateCachedInventoryResponse{}, nil
}

func dutsInCurrentEnvironment(ctx context.Context, duts []*inventory.DeviceUnderTest) []*inventory.DeviceUnderTest {
	// TODO(crbug.com/947322): Disable this temporarily until it
	// can be implemented properly.  This updates the cache of
	// DUTs which can only be queried by hostname or ID, so it is
	// not problematic to also cache DUTs in the wrong environment
	// (prod vs dev).
	return duts
}

func makeDroneConfigs(inf *inventory.Infrastructure, lab *inventory.Lab) []dronecfg.Entity {
	dutHostnames := makeDUTHostnameMap(lab.GetDuts())
	var entities []dronecfg.Entity
	for _, s := range inf.GetServers() {
		if !isDrone(s) {
			continue
		}
		e := dronecfg.Entity{
			Hostname: s.GetHostname(),
		}
		for _, d := range s.GetDutUids() {
			e.DUTs = append(e.DUTs, dronecfg.DUT{
				ID:       d,
				Hostname: dutHostnames[d],
			})
		}
		entities = append(entities, e)
	}
	return entities
}

// makeDUTHostnameMap makes a mapping from DUT IDs to DUT hostnames.
func makeDUTHostnameMap(duts []*inventory.DeviceUnderTest) map[string]string {
	m := make(map[string]string)
	for _, d := range duts {
		c := d.GetCommon()
		m[c.GetId()] = c.GetHostname()
	}
	return m
}

func isDrone(s *inventory.Server) bool {
	for _, r := range s.GetRoles() {
		if r == inventory.Server_ROLE_SKYLAB_DRONE {
			return true
		}
	}
	return false
}

func updateFreeDUTs(ctx context.Context, s *gitstore.InventoryStore) error {
	ic := newGlobalInvCache(ctx, s)
	var free []freeduts.DUT
	for dutID, d := range ic.idToDUT {
		if _, ok := ic.droneForDUT[dutID]; ok {
			continue
		}
		free = append(free, freeDUTInfo(d))
	}
	stale, err := getStaleFreeDUTs(ctx, free)
	if err != nil {
		return errors.Annotate(err, "update free duts").Err()
	}
	if err := freeduts.Remove(ctx, stale); err != nil {
		return errors.Annotate(err, "update free duts").Err()
	}
	if err := freeduts.Add(ctx, free); err != nil {
		return errors.Annotate(err, "update free duts").Err()
	}
	return nil
}

// getStaleFreeDUTs returns the free DUTs in datastore that are no longer
// free, given the currently free DUTs passed as an argument.
func getStaleFreeDUTs(ctx context.Context, free []freeduts.DUT) ([]freeduts.DUT, error) {
	freeMap := make(map[string]bool, len(free))
	for _, d := range free {
		freeMap[d.ID] = true
	}
	all, err := freeduts.GetAll(ctx)
	if err != nil {
		return nil, errors.Annotate(err, "get stale free duts").Err()
	}
	stale := make([]freeduts.DUT, 0, len(all))
	for _, d := range all {
		if _, ok := freeMap[d.ID]; !ok {
			stale = append(stale, d)
		}
	}
	return stale, nil
}

// freeDUTInfo returns the free DUT info to store for a DUT.
func freeDUTInfo(d *inventory.DeviceUnderTest) freeduts.DUT {
	c := d.GetCommon()
	rr := d.GetRemovalReason()
	var t time.Time
	if ts := rr.GetExpireTime(); ts != nil {
		t = time.Unix(ts.GetSeconds(), int64(ts.GetNanos())).UTC()
	}
	return freeduts.DUT{
		ID:         c.GetId(),
		Hostname:   c.GetHostname(),
		Bug:        rr.GetBug(),
		Comment:    rr.GetComment(),
		ExpireTime: t,
		Model:      c.GetLabels().GetModel(),
	}
}
