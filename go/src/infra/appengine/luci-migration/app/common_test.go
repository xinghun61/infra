// Copyright 2017 The LUCI Authors.
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
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/secrets/testsecrets"
	"go.chromium.org/luci/server/templates"
)

func testContext() context.Context {
	c := context.Background()
	c = memory.UseWithAppID(c, "dev~luci-migration-dev")
	c = logging.SetLevel(c, logging.Debug)
	c = gologger.StdConfig.Use(c)
	c = testsecrets.Use(c)
	c = templates.Use(c, prepareTemplates())
	c, _ = testclock.UseTime(c, time.Date(2016, time.February, 3, 4, 5, 6, 0, time.UTC))
	return c
}
