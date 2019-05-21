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

// Package arquebus is the entry point of this app.
package arquebus

import (
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/common/data/rand/mathrand"
	"go.chromium.org/luci/config/validation"
	"go.chromium.org/luci/server/router"

	"infra/appengine/arquebus/app/backend"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/cron"
	"infra/appengine/arquebus/app/frontend"
)

func init() {
	// Dev server likes to restart a lot, and upon a restart math/rand
	// seed is always set to 1, resulting in lots of presumably "random"
	// IDs not being very random. Seed it with real randomness.
	mathrand.SeedRandomly()

	// -------------------------
	// Install handlers
	// -------------------------
	r := router.New()
	m := standard.Base().Extend(config.Middleware)
	dispatcher := &tq.Dispatcher{BaseURL: "/internal/tq/"}

	standard.InstallHandlers(r)
	backend.InstallHandlers(r, dispatcher, m)
	frontend.InstallHandlers(r, m)
	cron.InstallHandlers(r, dispatcher, m)

	config.SetupValidation(&validation.Rules)
	http.DefaultServeMux.Handle("/", r)
}
