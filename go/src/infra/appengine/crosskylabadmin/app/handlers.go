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
	"infra/appengine/crosskylabadmin/app/cron"
	"infra/appengine/crosskylabadmin/app/frontend"
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/server/router"
)

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand seed is
	// always set to 1, resulting in lots of presumably "random" IDs not being
	// very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	r := router.New()
	mwBase := standard.Base()

	// Install auth, config and tsmon handlers.
	standard.InstallHandlers(r)
	frontend.InstallHandlers(r, standard.Base())
	cron.InstallHandlers(r, mwBase)

	http.DefaultServeMux.Handle("/", r)
}
