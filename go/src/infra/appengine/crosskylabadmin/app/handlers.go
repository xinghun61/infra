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

package app

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaeauth/server"
	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/grpc/discovery"
	"go.chromium.org/luci/grpc/grpcmon"
	"go.chromium.org/luci/grpc/grpcutil"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/crosskylabadmin/api/fleet/v1"
)

// These are app-wide constants related to the Swarming setup of ChromeOS Skylab.
// TODO(pprabhu): Use luci-config for these configuration options.
const (
	// luci-auth group controlling access to admin app APIs.
	accessGroup = "chromeos-skylab-bot-fleet-access"
	// Swarming instance hosting skylab bots.
	swarmingInstance = "chrome-swarming.appspot.com"
	// Swarming bot pool containing skylab bots.
	swarmingBotPool = "ChromeOSSkylab"
)

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	r := router.New()
	mwAuthenticated := standard.Base().Extend(
		auth.Authenticate(
			server.UsersAPIAuthMethod{},
			&server.OAuth2Method{Scopes: []string{server.EmailScope}},
		),
	)

	// Install auth, config and tsmon handlers.
	standard.InstallHandlers(r)

	api := prpc.Server{
		UnaryServerInterceptor: grpcmon.NewUnaryServerInterceptor(grpcutil.NewUnaryServerPanicCatcher(nil)),
	}
	fleet.RegisterTrackerServer(&api, &fleet.DecoratedTracker{
		Service: &trackerServerImpl{},
		Prelude: checkAccess,
	})
	fleet.RegisterTaskerServer(&api, &fleet.DecoratedTasker{
		Service: &taskerServerImpl{},
		Prelude: checkAccess,
	})

	discovery.Enable(&api)
	api.InstallHandlers(r, mwAuthenticated)
	http.DefaultServeMux.Handle("/", r)
}

// grpcfyRawErrors converts errors to grpc errors.
func grpcfyRawErrors(err error) error {
	if status.Code(err) == codes.Unknown {
		return status.Errorf(codes.Internal, err.Error())
	}
	return err
}
