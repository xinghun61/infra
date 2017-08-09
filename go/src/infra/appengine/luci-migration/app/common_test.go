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
