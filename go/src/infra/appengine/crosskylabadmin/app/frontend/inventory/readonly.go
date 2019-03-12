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
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/dronecfg"
	dsinventory "infra/appengine/crosskylabadmin/app/frontend/internal/datastore/inventory"
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

	if err := req.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	var spec []byte
	if req.Id != "" {
		spec, err = dsinventory.GetSerializedDUTByID(ctx, req.Id)
	} else {
		spec, err = dsinventory.GetSerializedDUTByHostname(ctx, req.Hostname)
	}

	if err != nil {
		if datastore.IsErrNoSuchEntity(err) {
			return nil, status.Errorf(codes.NotFound, err.Error())
		}
		return nil, err
	}
	return &fleet.GetDutInfoResponse{Spec: spec}, nil
}

// GetDroneConfig implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) GetDroneConfig(ctx context.Context, req *fleet.GetDroneConfigRequest) (resp *fleet.GetDroneConfigResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Errorf(codes.Unimplemented, "not yet implemented")
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
	return &fleet.UpdateCachedInventoryResponse{}, nil
}

func dutsInCurrentEnvironment(ctx context.Context, duts []*inventory.DeviceUnderTest) []*inventory.DeviceUnderTest {
	env := config.Get(ctx).Inventory.Environment
	filtered := make([]*inventory.DeviceUnderTest, 0, len(duts))
	for _, d := range duts {
		if d.GetCommon().GetEnvironment().String() == env {
			filtered = append(filtered, d)
		}
	}
	return filtered
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
