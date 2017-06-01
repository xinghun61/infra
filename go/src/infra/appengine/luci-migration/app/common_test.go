package app

import (
	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	memcfg "github.com/luci/luci-go/common/config/impl/memory"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/luci_config/server/cfgclient/backend/testconfig"
	"github.com/luci/luci-go/server/secrets/testsecrets"
	"github.com/luci/luci-go/server/templates"
)

func testContext() context.Context {
	c := context.Background()
	c = memory.UseWithAppID(c, "dev~luci-migration-dev")
	c = logging.SetLevel(c, logging.Debug)
	c = gologger.StdConfig.Use(c)
	c = testsecrets.Use(c)
	c = templates.Use(c, prepareTemplates())
	return c
}

func useConfig(c context.Context, text string) context.Context {
	return testconfig.WithCommonClient(c, memcfg.New(map[string]memcfg.ConfigSet{
		"services/luci-migration-dev": {
			"config.cfg": text,
		},
	}))
}
