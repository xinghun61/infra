package som

import (
	"encoding/json"
	"fmt"
	"net/http"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

func getAnalyzeHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	gkRules, err := getGatekeeperRules(c)
	if err != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("getting gatekeeper trees: %v", err))
		return
	}

	treeCfg, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("unrecoginzed tree: %s", tree))
		return
	}

	a := analyzer.New(5, 100)
	a.Gatekeeper = gkRules
	// TODO(seanmccullough): Set a.MasterOnly, BuilderOnly, Build etc based on Params.

	if client.GetReader(c) == nil {
		miloReader := client.NewMiloReader(c, "")
		c = client.WithReader(c, miloReader)
	}

	alerts := []messages.Alert{}
	for masterLoc := range treeCfg.Masters {
		buildExtract, err := client.BuildExtract(c, &masterLoc)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
			return
		}
		masterAlerts := a.MasterAlerts(c, &masterLoc, buildExtract)
		builderAlerts := a.BuilderAlerts(c, tree, &masterLoc, buildExtract)
		alerts = append(alerts, masterAlerts...)
		alerts = append(alerts, builderAlerts...)
	}

	b, err := json.Marshal(alerts)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(b)
}
