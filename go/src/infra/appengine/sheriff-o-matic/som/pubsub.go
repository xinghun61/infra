package som

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"fmt"
	"net/http"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"
	sompubsub "infra/monitoring/pubsubalerts"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

const (
	gkConfigURL         = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper.json?format=text"
	gkTreesURL          = "https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper_trees.json?format=text"
	gkConfigCorpURL     = "https://chrome-internal.googlesource.com/chrome/tools/build/+/master/scripts/slave-internal/gatekeeper_corp.json?format=text"
	gkTreesCorpURL      = "https://chrome-internal.googlesource.com/chrome/tools/build/+/master/scripts/slave-internal/gatekeeper_trees_corp.json?format=text"
	gkConfigInternalURL = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/gatekeeper_internal.json?format=text"
	gkTreesInternalURL  = "https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave/+/master/gatekeeper_trees_internal.json?format=text"
)

// This is what we get from the Data field of the pubsub push request body.
type buildMasterMsg struct {
	Master *messages.BuildExtract `json:"master"`
	Builds []*messages.Build      `json:"builds"`
}

type pushMessage struct {
	Attributes map[string]string
	Data       []byte
	ID         string `json:"message_id"`
}

type pushRequest struct {
	Message      pushMessage
	Subscription string
}

func postMiloPubSubHandler(ctx *router.Context) {
	c, w, r := ctx.Context, ctx.Writer, ctx.Request
	msg := &pushRequest{}
	if err := json.NewDecoder(r.Body).Decode(msg); err != nil {
		logging.Errorf(c, "Could not json decode body: %v", err)
		return
	}

	reader, err := zlib.NewReader(bytes.NewReader(msg.Message.Data))
	if err != nil {
		logging.Errorf(c, "Could not zlib decode message data: %v", err)
		return
	}

	dec := json.NewDecoder(reader)
	extract := buildMasterMsg{}
	if err = dec.Decode(&extract); err != nil {
		logging.Errorf(c, "Could not decode build extract: %v", err)
		return
	}

	if len(extract.Builds) == 0 {
		return
	}

	if extract.Master != nil {
		logging.Debugf(c, "Contains %d builds for %d builders.", len(extract.Builds), len(extract.Master.Builders))
	}

	store := sompubsub.NewAlertStore()
	gkRules, err := getGatekeeperRules(c)
	if err != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err)
		return
	}

	miloPubSubHandler := &sompubsub.BuildHandler{
		Store:           store,
		GatekeeperRules: gkRules,
	}

	for _, b := range extract.Builds {
		if err := miloPubSubHandler.HandleBuild(c, b); err != nil {
			logging.Errorf(c, "Could not handle build: %v", err)
		}
	}

	w.Write([]byte("ok"))
}

func getPubSubAlertsHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	store := sompubsub.NewAlertStore()
	trees, err := getGatekeeperTrees(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	treeCfg, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("Unrecoginzed tree: %s", tree))
		return
	}

	activeAlerts := []*messages.Alert{}

	for masterLoc := range treeCfg.Masters {
		alerts, err := store.ActiveAlertsForBuilder(c, masterLoc.Name(), "")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}
		for _, a := range alerts {
			alert := &messages.Alert{
				// TODO(seanmccullough): Fill out the rest of this with actual
				// failure details etc.
				Title: a.Signature,
			}
			activeAlerts = append(activeAlerts, alert)
		}
	}

	b, err := json.Marshal(activeAlerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}

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
// Blocked on https://bugs.chromium.org/p/chromium/issues/detail?id=658270
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
