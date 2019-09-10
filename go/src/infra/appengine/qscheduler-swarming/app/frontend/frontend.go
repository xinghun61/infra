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
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// SkipAuthorization is set to true when running in dev server locally.
var SkipAuthorization = false

type role int

const (
	roleAdmin role = iota
	roleSwarming
	roleView
)

// InstallServices installs the services implemented by the frontend package.
func InstallServices(apiServer *prpc.Server) {
	swarming.RegisterExternalSchedulerServer(apiServer, &swarming.DecoratedExternalScheduler{
		Service: NewBatchedServer(),
		Prelude: accessChecker(roleSwarming),
	})
	qscheduler.RegisterQSchedulerAdminServer(apiServer, &qscheduler.DecoratedQSchedulerAdmin{
		Service: &QSchedulerAdminServerImpl{},
		Prelude: accessChecker(roleAdmin),
	})
	qscheduler.RegisterQSchedulerViewServer(apiServer, &qscheduler.DecoratedQSchedulerView{
		Service: &QSchedulerViewServerImpl{},
		Prelude: accessChecker(roleView, roleAdmin),
	})
}

// groupFor determines the configured group name for a given role.
func groupFor(r role, auth *config.Auth) (group string) {
	switch r {
	case roleAdmin:
		return auth.AdminGroup
	case roleSwarming:
		return auth.SwarmingGroup
	case roleView:
		return auth.ViewGroup
	default:
		return ""
	}
}

// groupsFor determined configured group names for the given roles.
func groupsFor(rs []role, auth *config.Auth) []string {
	groups := make([]string, 0, len(rs))
	for _, r := range rs {
		groups = append(groups, groupFor(r, auth))
	}
	return groups
}

// accessChecker returns a Prelude function that ensures the the caller is granted
// one of the given roles.
func accessChecker(allowedRoles ...role) func(context.Context, string, proto.Message) (context.Context, error) {
	checker := func(c context.Context, _ string, _ proto.Message) (context.Context, error) {
		if SkipAuthorization {
			return c, nil
		}
		config := config.Get(c)
		if config == nil {
			return c, status.Errorf(codes.PermissionDenied, "no auth configured: permission denied")
		}
		a := config.Auth
		if a == nil {
			return c, status.Errorf(codes.PermissionDenied, "no auth configured: permission denied")
		}

		groups := groupsFor(allowedRoles, a)
		allow, err := auth.IsMember(c, groups...)

		if err != nil {
			return c, status.Errorf(codes.Internal, "can't check ACL - %s", err)
		}

		if allow {
			return c, nil
		}

		return c, status.Errorf(codes.PermissionDenied, "permission denied")
	}

	return checker
}
