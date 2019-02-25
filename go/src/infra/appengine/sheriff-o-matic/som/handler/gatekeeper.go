package handler

import (
	"encoding/json"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/monitoring/messages"

	"golang.org/x/net/context"
)

const (
	gkConfigURL         = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/recipe_modules/gatekeeper/resources/gatekeeper.json?format=text"
	gkTreesURL          = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/recipe_modules/gatekeeper/resources/gatekeeper_trees.json?format=text"
	gkConfigInternalURL = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/recipes/gatekeeper_internal.resources/gatekeeper_internal.json?format=text"
	gkTreesInternalURL  = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/recipes/gatekeeper_internal.resources/gatekeeper_trees_internal.json?format=text"
	gkUnkeptConfigURL   = "https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/appengine/sheriff-o-matic/config/unkept_gatekeeper.json?format=text"
	gkUnkeptTreesURL    = "https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/appengine/sheriff-o-matic/config/unkept_gatekeeper_trees.json?format=text"
)

func getGatekeeperRules(c context.Context) (*analyzer.GatekeeperRules, error) {
	cfgs, err := getGatekeeperConfigs(c)
	if err != nil {
		return nil, err
	}

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		return nil, err
	}

	return analyzer.NewGatekeeperRules(c, cfgs, trees), nil
}

func getGatekeeperConfigs(c context.Context) ([]*messages.GatekeeperConfig, error) {
	ret := []*messages.GatekeeperConfig{}
	for _, URL := range []string{gkConfigURL, gkConfigInternalURL, gkUnkeptConfigURL} {
		b, err := client.GetGitilesCached(c, URL)
		if err != nil {
			return nil, err
		}

		gk := &messages.GatekeeperConfig{}
		if err := json.Unmarshal(b, gk); err != nil {
			return nil, err
		}
		ret = append(ret, gk)
	}

	return ret, nil
}

// TODO(seanmccullough): Replace this urlfetch/memcache code with a luci-config reader.
func getGatekeeperTrees(c context.Context) (map[string][]messages.TreeMasterConfig, error) {
	ret := map[string][]messages.TreeMasterConfig{}

	for _, URL := range []string{gkTreesURL, gkTreesInternalURL, gkUnkeptTreesURL} {
		gkBytes, err := client.GetGitilesCached(c, URL)
		if err != nil {
			return nil, err
		}

		treeCfg := map[string]messages.TreeMasterConfig{}
		if err := json.Unmarshal(gkBytes, &treeCfg); err != nil {
			return nil, err
		}

		// Merge tree configs if the same tree name appears in mulitiple files.
		for name, cfg := range treeCfg {
			if ret[name] == nil {
				ret[name] = []messages.TreeMasterConfig{}
			}
			ret[name] = append(ret[name], cfg)
		}
	}

	return ret, nil
}
