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
	dsinventory "infra/appengine/crosskylabadmin/app/frontend/internal/datastore/inventory"
)

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
	if err := dsinventory.UpdateDUTs(ctx, store.Lab.GetDuts()); err != nil {
		return nil, err
	}
	return &fleet.UpdateCachedInventoryResponse{}, nil
}
