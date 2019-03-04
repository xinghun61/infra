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
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"

	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GetDutInfo implements the method from fleet.InventoryServer interface.
func (*ServerImpl) GetDutInfo(ctx context.Context, req *fleet.GetDutInfoRequest) (*fleet.GetDutInfoResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "not yet implemented")
}

// UpdateCachedInventory implements the method from fleet.InventoryServer interface.
func (*ServerImpl) UpdateCachedInventory(ctx context.Context, req *fleet.UpdateCachedInventoryRequest) (*fleet.UpdateCachedInventoryResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "not yet implemented")
}
