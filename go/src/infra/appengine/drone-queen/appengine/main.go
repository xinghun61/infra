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

package appengine

import (
	crand "crypto/rand"
	"encoding/binary"
	"math/rand"
	"net/http"

	"go.chromium.org/luci/appengine/gaemiddleware/standard"
	"go.chromium.org/luci/config/validation"
	"go.chromium.org/luci/server/router"

	"infra/appengine/drone-queen/internal/config"
	"infra/appengine/drone-queen/internal/cron"
	"infra/appengine/drone-queen/internal/frontend"
)

func init() {
	seedRand()
	setupConfigValidation()

	r := router.New()
	standard.InstallHandlers(r)
	mw := standard.Base().Extend(config.Middleware)
	cron.InstallHandlers(r, mw)
	frontend.InstallHandlers(r, mw)
	http.DefaultServeMux.Handle("/", r)
}

func seedRand() {
	var b [8]byte
	if _, err := crand.Read(b[:]); err != nil {
		panic(err)
	}
	rand.Seed(int64(binary.LittleEndian.Uint64(b[:])))
}

func setupConfigValidation() {
	validation.Rules.Add("services/${appid}", config.File, config.Validate)
}
