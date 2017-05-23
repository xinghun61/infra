package som

import (
	"encoding/json"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"golang.org/x/net/context"
)

const (
	gkConfigURL         = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper.json?format=text"
	gkTreesURL          = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper_trees.json?format=text"
	gkConfigCorpURL     = "https://chrome-internal.googlesource.com/chrome/tools/build/+/master/scripts/slave-internal/gatekeeper_corp.json?format=text"
	gkTreesCorpURL      = "https://chrome-internal.googlesource.com/chrome/tools/build/+/master/scripts/slave-internal/gatekeeper_trees_corp.json?format=text"
	gkConfigInternalURL = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/gatekeeper_internal.json?format=text"
	gkTreesInternalURL  = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/gatekeeper_trees_internal.json?format=text"
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

	// TODO(seanmccullough): Clean up this API.
	adjustedTrees := map[string][]messages.TreeMasterConfig{}
	for treeName, cfg := range trees {
		adjustedTrees[treeName] = []messages.TreeMasterConfig{*cfg}
	}

	return analyzer.NewGatekeeperRules(c, cfgs, adjustedTrees), nil
}

func getGatekeeperConfigs(c context.Context) ([]*messages.GatekeeperConfig, error) {
	ret := []*messages.GatekeeperConfig{}
	for _, URL := range []string{gkConfigURL, gkConfigInternalURL, gkConfigCorpURL} {
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
var getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
	ret := map[string]*messages.TreeMasterConfig{}

	for _, URL := range []string{gkTreesURL, gkTreesInternalURL, gkTreesCorpURL} {
		gkBytes, err := client.GetGitilesCached(c, URL)
		if err != nil {
			return nil, err
		}

		// TODO: make sure this doesn't blow away map values from previous iterations.
		if err := json.Unmarshal(gkBytes, &ret); err != nil {
			return nil, err
		}
	}

	return ret, nil
}
