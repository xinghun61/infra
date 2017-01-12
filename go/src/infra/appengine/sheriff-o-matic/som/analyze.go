package som

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sort"
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

type bySeverity []messages.Alert

func (a bySeverity) Len() int      { return len(a) }
func (a bySeverity) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a bySeverity) Less(i, j int) bool {
	return a[i].Severity < a[j].Severity
}

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
	logging.Infof(c, "Getting compressed master json for %d masters", len(treeCfg.Masters))

	type res struct {
		alerts []messages.Alert
		err    error
	}

	resCh := make(chan res)
	for masterLoc := range treeCfg.Masters {
		masterLoc := masterLoc
		go func() {
			buildExtract, err := client.BuildExtract(c, &masterLoc)
			r := res{err: err}
			if err == nil {
				r.alerts = a.MasterAlerts(c, &masterLoc, buildExtract)
				r.alerts = append(r.alerts, a.BuilderAlerts(c, tree, &masterLoc, buildExtract)...)
			}
			resCh <- r
		}()
	}

	var anyErr error
	for i := 0; i < len(treeCfg.Masters); i++ {
		r := <-resCh
		alerts = append(alerts, r.alerts...)
		if r.err != nil {
			anyErr = r.err
		}
	}

	if anyErr != nil {
		// TODO: Deal with partial failures so some errors are tolerated so long
		// as some analysis succeeded.
		errStatus(c, w, http.StatusInternalServerError, anyErr.Error())
		return
	}

	if err := storeAlertsSummary(c, a, tree, &messages.AlertsSummary{
		RevisionSummaries: map[string]messages.RevisionSummary{},
		Alerts:            alerts,
	}); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
	}

	w.Write([]byte("ok"))
}

func storeAlertsSummary(c context.Context, a *analyzer.Analyzer, tree string, alertsSummary *messages.AlertsSummary) error {
	sort.Sort(messages.Alerts(alertsSummary.Alerts))
	sort.Stable(bySeverity(alertsSummary.Alerts))

	// Make sure we have summaries for each revision implicated in a builder failure.
	for _, alert := range alertsSummary.Alerts {
		if bf, ok := alert.Extension.(messages.BuildFailure); ok {
			for _, r := range bf.RegressionRanges {
				revs, err := a.GetRevisionSummaries(r.Revisions)
				if err != nil {
					return err
				}
				for _, rev := range revs {
					alertsSummary.RevisionSummaries[rev.GitHash] = rev
				}
			}
		}
	}
	alertsSummary.Timestamp = messages.TimeToEpochTime(time.Now())

	b, err := json.MarshalIndent(alertsSummary, "", "\t")
	if err != nil {
		return err
	}

	alertsJSON := &AlertsJSON{
		Tree:     datastore.MakeKey(c, "Tree", "milo."+tree),
		Date:     clock.Now(c).UTC(),
		Contents: b,
	}

	return datastore.Put(c, alertsJSON)
}
