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

// Package appengine is the entry point of this app.
// Appengine requires the entry point to be a leaf package.
package appengine

import (
	"net/http"

	"infra/appengine/qscheduler-swarming/app/config"
	"infra/appengine/qscheduler-swarming/app/cron"
	"infra/appengine/qscheduler-swarming/app/frontend"

	"google.golang.org/appengine"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/server/router"
)

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	// Don't check groups when running on devserver, for simplicity.
	frontend.SkipAuthorization = appengine.IsDevAppServer()

	r := router.New()
	mwBase := standard.Base().Extend(config.MiddlewareForGAE)

	// Install auth, config and tsmon handlers.
	standard.InstallHandlers(r)
	frontend.InstallHandlers(r, mwBase)
	cron.InstallHandlers(r, mwBase)

	config.SetupValidation()

	http.DefaultServeMux.Handle("/", r)
}
