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

// Package frontend exposes the primary pRPC API of qscheduler app.
package frontend

import (
	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/config"
	"infra/swarming"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/grpc/grpcmon"
	"go.chromium.org/luci/grpc/grpcutil"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// InstallHandlers installs the handlers implemented by the frontend package.
func InstallHandlers(r *router.Router, mwBase router.MiddlewareChain) {
	apiServer := prpc.Server{
		UnaryServerInterceptor: grpcmon.NewUnaryServerInterceptor(grpcutil.NewUnaryServerPanicCatcher(nil)),
	}
	swarming.RegisterExternalSchedulerServer(&apiServer, &swarming.DecoratedExternalScheduler{
		Service: &QSchedulerServerImpl{},
		Prelude: checkUserAccess,
	})
	qscheduler.RegisterQSchedulerAdminServer(&apiServer, &qscheduler.DecoratedQSchedulerAdmin{
		Service: &QSchedulerAdminServerImpl{},
		Prelude: checkAdminAccess,
	})

	discovery.Enable(&apiServer)

	mwAuthenticated := mwBase.Extend(
		auth.Authenticate(
			server.UsersAPIAuthMethod{},
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		),
	)
	apiServer.InstallHandlers(r, mwAuthenticated)
}

// TODO(akeshet): Remove the code duplication between these various access
// check functions.

// checkAdminAccess verifies that the request is from an authorized admin.
func checkAdminAccess(c context.Context, _ string, _ proto.Message) (context.Context, error) {
	a := config.Get(c).Auth
	if a == nil {
		return c, status.Errorf(codes.PermissionDenied, "no auth configured: permission denied")
	}

	switch allow, err := auth.IsMember(c, a.AdminGroup); {
	case err != nil:
		return c, status.Errorf(codes.Internal, "can't check ACL - %s", err)
	case !allow:
		return c, status.Errorf(codes.PermissionDenied, "permission denied")
	}
	return c, nil
}

// checkUserAccess verifies that the request is from an authorized user.
func checkUserAccess(c context.Context, _ string, _ proto.Message) (context.Context, error) {
	a := config.Get(c).Auth
	if a == nil {
		return c, status.Errorf(codes.PermissionDenied, "no auth configured: permission denied")
	}

	switch allow, err := auth.IsMember(c, a.SwarmingGroup); {
	case err != nil:
		return c, status.Errorf(codes.Internal, "can't check ACL - %s", err)
	case !allow:
		return c, status.Errorf(codes.PermissionDenied, "permission denied")
	}
	return c, nil
}
