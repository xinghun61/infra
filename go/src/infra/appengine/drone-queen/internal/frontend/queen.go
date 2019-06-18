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

package frontend

import (
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/drone-queen/api"
)

// DroneQueenImpl implements service interfaces.
type DroneQueenImpl struct{}

// ReportDrone implements service interfaces.
func (q *DroneQueenImpl) ReportDrone(ctx context.Context, req *api.ReportDroneRequest) (res *api.ReportDroneResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Errorf(codes.Unimplemented, "Unimplemented")
}

// ReleaseDuts implements service interfaces.
func (q *DroneQueenImpl) ReleaseDuts(ctx context.Context, req *api.ReleaseDutsRequest) (res *api.ReleaseDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Errorf(codes.Unimplemented, "Unimplemented")
}

// DeclareDuts implements service interfaces.
func (q *DroneQueenImpl) DeclareDuts(ctx context.Context, req *api.DeclareDutsRequest) (res *api.DeclareDutsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	return nil, status.Errorf(codes.Unimplemented, "Unimplemented")
}
