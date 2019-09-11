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
	"context"
	"flag"
	"time"

	"infra/appengine/qscheduler-swarming/app/config"
	"infra/appengine/qscheduler-swarming/app/eventlog"
	"infra/appengine/qscheduler-swarming/app/frontend"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server"
)

func main() {
	cfgLoader := config.Loader{}
	cfgLoader.RegisterFlags(flag.CommandLine)

	server.Main(nil, func(srv *server.Server) error {
		// Don't check groups when running in dev mode, for simplicity.
		frontend.SkipAuthorization = !srv.Options.Prod

		// Load qscheduler service config form a local file (deployed via GKE),
		// periodically reread it to pick up changes without full restart.
		if _, err := cfgLoader.Load(); err != nil {
			return err
		}
		srv.RunInBackground("qscheduler.config", cfgLoader.ReloadLoop)

		// Periodically cleanup old nodestore entities.
		srv.RunInBackground("qscheduler.cleanup", cleanupNodestore)

		bi, err := eventlog.NewRAMBufferedBQInserter(srv.Context,
			srv.Options.CloudProject, eventlog.DatasetID, eventlog.TableID)
		if err != nil {
			return err
		}
		srv.RegisterCleanup(func() { bi.CloseAndDrain(srv.Context) })

		// Make config and eventlog implementations available to all handlers.
		srv.Context = config.Use(srv.Context, cfgLoader.Config)
		srv.Context = eventlog.Use(srv.Context, bi)

		// Install main API services.
		frontend.InstallServices(srv.PRPC)
		return nil
	})
}

// cleanupNodestore runs as a background goroutine to cleanup old entities.
func cleanupNodestore(ctx context.Context) {
	for {
		clockResult := <-clock.After(ctx, 1*time.Minute)
		if clockResult.Err != nil {
			// Context was cancelled.
			logging.Errorf(ctx, "cleanup loop terminating: %s", clockResult.Err)
			return
		}

		IDs, err := nodestore.List(ctx)
		if err != nil {
			logging.Errorf(ctx, "cleanup loop: list: %s", err.Error())
			continue
		}

		for _, ID := range IDs {
			s := nodestore.New(ID)

			cctx, cancel := context.WithTimeout(ctx, 5*time.Minute)
			cleaned, err := s.Clean(cctx)
			cancel()

			if err == nil {
				logging.Infof(ctx, "cleanup loop: pool %s: cleaned %d entities", ID, cleaned)
			} else {
				logging.Errorf(ctx, "cleanup loop: pool %s: %s", ID, err.Error())
			}
		}
	}
}
