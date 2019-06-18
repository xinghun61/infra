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

// Package frontend implements the drone queen service.
package frontend

import (
	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/grpc/grpcmon"
	"go.chromium.org/luci/grpc/grpcutil"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/drone-queen/api"
	"infra/appengine/drone-queen/internal/config"
)

// InstallHandlers installs the handlers implemented by the frontend package.
func InstallHandlers(r *router.Router, mw router.MiddlewareChain) {
	var si grpc.UnaryServerInterceptor
	si = grpcutil.NewUnaryServerPanicCatcher(si)
	si = grpcmon.NewUnaryServerInterceptor(si)
	s := prpc.Server{
		UnaryServerInterceptor: si,
	}
	var q DroneQueenImpl
	api.RegisterDroneServer(&s, &api.DecoratedDrone{
		Service: &q,
		Prelude: checkDroneAccess,
	})
	api.RegisterInventoryProviderServer(&s, &api.DecoratedInventoryProvider{
		Service: &q,
		Prelude: checkInventoryProviderAccess,
	})
	discovery.Enable(&s)
	s.InstallHandlers(r, mw)
}

func checkDroneAccess(ctx context.Context, _ string, _ proto.Message) (context.Context, error) {
	g := config.Get(ctx).GetAccessGroups()
	allow, err := auth.IsMember(ctx, g.GetDrones())
	if err != nil {
		return ctx, status.Errorf(codes.Internal, "can't check access group membership: %s", err)
	}
	if !allow {
		return ctx, status.Errorf(codes.PermissionDenied, "permission denied")
	}
	return ctx, nil
}

func checkInventoryProviderAccess(ctx context.Context, _ string, _ proto.Message) (context.Context, error) {
	g := config.Get(ctx).GetAccessGroups()
	allow, err := auth.IsMember(ctx, g.GetInventoryProviders())
	if err != nil {
		return ctx, status.Errorf(codes.Internal, "can't check access group membership: %s", err)
	}
	if !allow {
		return ctx, status.Errorf(codes.PermissionDenied, "permission denied")
	}
	return ctx, nil
}
