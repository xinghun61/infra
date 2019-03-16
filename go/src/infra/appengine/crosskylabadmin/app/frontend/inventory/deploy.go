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

package inventory

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"

	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// DeployDut implements the method from fleet.InventoryServer interface.
func (*ServerImpl) DeployDut(ctx context.Context, req *fleet.DeployDutRequest) (*fleet.DeployDutResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "deploy dut: not implemented yet")
}

// RedeployDut implements the method from fleet.InventoryServer interface.
func (*ServerImpl) RedeployDut(ctx context.Context, req *fleet.RedeployDutRequest) (*fleet.RedeployDutResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "redeploy dut: not implemented yet")
}

// GetDeploymentStatus implements the method from fleet.InventoryServer interface.
func (*ServerImpl) GetDeploymentStatus(ctx context.Context, req *fleet.GetDeploymentStatusRequest) (*fleet.GetDeploymentStatusResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "get deployment status: not implemented yet")
}

// DeleteDuts implements the method from fleet.InventoryServer interface.
func (*ServerImpl) DeleteDuts(ctx context.Context, req *fleet.DeleteDutsRequest) (*fleet.DeleteDutsResponse, error) {
	return nil, status.Errorf(codes.Unimplemented, "delete duts: not implemented yet")
}
