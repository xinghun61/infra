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
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"

	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/grpc/grpcutil"
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
func (is *ServerImpl) DeleteDuts(ctx context.Context, req *fleet.DeleteDutsRequest) (resp *fleet.DeleteDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = req.Validate(); err != nil {
		return nil, err
	}
	s, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	var changeURL string
	var removedIDs []string
	f := func() (err error) {
		if err := s.Refresh(ctx); err != nil {
			return err
		}
		removedDUTs := removeDUTWithHostnames(s, req.Hostnames)
		url, err := s.Commit(ctx, fmt.Sprintf("delete %d duts", len(removedDUTs)))
		if err != nil {
			return err
		}

		// Captured variables only on success, hence at most once.
		changeURL = url
		removedIDs = make([]string, 0, len(removedDUTs))
		for _, d := range removedDUTs {
			removedIDs = append(removedIDs, d.GetCommon().GetId())
		}
		return nil
	}
	if err = retry.Retry(ctx, transientErrorRetries(), f, retry.LogCallback(ctx, "DeleteDut")); err != nil {
		return nil, err
	}

	return &fleet.DeleteDutsResponse{
		ChangeUrl: changeURL,
		Ids:       removedIDs,
	}, nil

}

// removeDUTWithHostnames deletes duts with the given hostnames.
//
// The function returns the deleted duts.
// If multiple DUTs have the same hostname, that is in hostnames, they are all deleted.
func removeDUTWithHostnames(s *gitstore.InventoryStore, hostnames []string) []*inventory.DeviceUnderTest {
	duts := s.Lab.Duts
	toRemove := stringset.NewFromSlice(hostnames...)
	removedDuts := make([]*inventory.DeviceUnderTest, 0, len(hostnames))
	for i := 0; i < len(duts); {
		d := duts[i]
		h := d.GetCommon().GetHostname()
		if !toRemove.Has(h) {
			i++
			continue
		}
		removedDuts = append(removedDuts, d)
		duts = deleteAtIndex(duts, i)
	}
	s.Lab.Duts = duts
	return removedDuts
}

func deleteAtIndex(duts []*inventory.DeviceUnderTest, i int) []*inventory.DeviceUnderTest {
	copy(duts[i:], duts[i+1:])
	duts[len(duts)-1] = nil
	return duts[:len(duts)-1]
}
