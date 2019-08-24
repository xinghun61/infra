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

// Command qscheduler-swarming implements a qscheduler server process for GKE
// environment.
package main

import (
	"flag"
	"os"

	"infra/appengine/qscheduler-swarming/app/config"
	"infra/appengine/qscheduler-swarming/app/eventlog"
	"infra/appengine/qscheduler-swarming/app/frontend"

	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/hardcoded/chromeinfra"
	"go.chromium.org/luci/server"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

func main() {
	mathrand.SeedRandomly()

	// Use OAuth2 as default authentication method for incoming pRPC calls.
	prpc.RegisterDefaultAuth(&auth.Authenticator{
		Methods: []auth.Method{
			&auth.GoogleOAuth2Method{
				Scopes: []string{"https://www.googleapis.com/auth/userinfo.email"},
			},
		},
	})

	cfgLoader := config.Loader{}
	cfgLoader.RegisterFlags(flag.CommandLine)

	// Instantiate the LUCI server instance based on CLI flags.
	opts := server.Options{
		ClientAuth: chromeinfra.DefaultAuthOptions(),
	}
	opts.Register(flag.CommandLine)
	flag.Parse()
	srv := server.New(opts)

	// Don't check groups when running in dev mode, for simplicity.
	frontend.SkipAuthorization = !opts.Prod

	// Load qscheduler service config form a local file (deployed via GKE),
	// periodically reread it to pick up changes without full restart.
	if _, err := cfgLoader.Load(); err != nil {
		srv.Fatal(err)
	}
	srv.RunInBackground("qscheduler.config", cfgLoader.ReloadLoop)

	nullBQInserter := eventlog.NullBQInserter{}
	base := router.NewMiddlewareChain(cfgLoader.Install(), nullBQInserter.Install())

	// Install qscheduler HTTP routes.
	frontend.InstallHandlers(srv.Routes, base)

	// Start the serving loop.
	if err := srv.ListenAndServe(); err != nil {
		os.Exit(1)
	}
}
