package som

import (
	"fmt"
	"net/http"
	"sort"
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
	dmp "github.com/sergi/go-diff/diffmatchpatch"
)

var (
	alertDiffs = metric.NewCounter("analyzer/cron_alert_diffs",
		"Number of diffs between alerts-dispatcher and cron alerts json", nil,
		field.String("tree"))
)

var errStatus = func(c context.Context, w http.ResponseWriter, status int, msg string) {
	logging.Errorf(c, "Status %d msg %s", status, msg)
	w.WriteHeader(status)
	w.Write([]byte(msg))
}

type bySeverity []messages.Alert

func (a bySeverity) Len() int      { return len(a) }
func (a bySeverity) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a bySeverity) Less(i, j int) bool {
	return a[i].Severity < a[j].Severity
}

// GetAnalyzeHandler enqueues a request to run an analysis on a particular tree.
// This is usually hit by appengine cron rather than manually.
func GetAnalyzeHandler(ctx *router.Context) {
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

	treeCfgs, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("unrecoginzed tree: %s", tree))
		return
	}

	logging.Debugf(c, "%s tree has %d configs", tree, len(treeCfgs))

	a := analyzer.New(5, 100)
	a.Gatekeeper = gkRules

	if client.GetReader(c) == nil {
		transport, err := auth.GetRPCTransport(c, auth.AsSelf)
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error getting transport: %v", err))
			return
		}

		c = urlfetch.Set(c, transport)

		miloReader, err := client.NewMiloReader(c, "")
		if err != nil {
			errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("error creating milo client: %v", err))
			return
		}
		memcachingReader := client.NewMemcacheReader(miloReader)
		c = client.WithReader(c, memcachingReader)
	}

	alerts := []messages.Alert{}
	for _, treeCfg := range treeCfgs {
		logging.Debugf(c, "Getting compressed master json for %d masters", len(treeCfg.Masters))

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
	}

	logging.Debugf(c, "storing %d alerts for %s", len(alerts), tree)

	if err := storeAlertsSummary(c, a, tree, &messages.AlertsSummary{
		RevisionSummaries: map[string]messages.RevisionSummary{},
		Alerts:            alerts,
	}); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
	}

	// This is just to measure the tsmon metric for number of diffs.
	_, _, _ = getMiloDiffs(c, tree)
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

	// TODO(seanmccullough): remove "milo." prefix.
	return putAlertsDatastore(c, "milo."+tree, alertsSummary, true)
}

func getMiloDiffs(c context.Context, tree string) (*dmp.DiffMatchPatch, []dmp.Diff, error) {
	oldAlerts, err := getAlertsForTree(c, tree)
	if err != nil {
		return nil, nil, err
	}

	newAlerts, err := getAlertsForTree(c, "milo."+tree)
	if err != nil {
		return nil, nil, err
	}

	differ := dmp.New()
	diffs := differ.DiffMain(string(oldAlerts.Contents), string(newAlerts.Contents), true)
	alertDiffs.Add(c, int64(differ.DiffLevenshtein(diffs)), tree)
	return differ, diffs, nil
}

// GetMiloDiffHandler will render an html pretty-printed diff of the alert sets
// for a given tree, created by alerts dispatcher and GetAnalyzeHandler, respectively.
func GetMiloDiffHandler(ctx *router.Context) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, fmt.Sprintf("getting gatekeeper trees: %v", err))
		return
	}

	_, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("unrecoginzed tree: %s", tree))
		return
	}

	differ, diffs, err := getMiloDiffs(c, tree)
	if err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Write([]byte(differ.DiffPrettyHtml(diffs)))
}

func getAlertsForTree(c context.Context, tree string) (*AlertsJSON, error) {
	results := []*AlertsJSON{}
	q := datastore.NewQuery("AlertsJSON")
	q = q.Ancestor(datastore.MakeKey(c, "Tree", tree))
	q = q.Order("-Date")
	q = q.Limit(1)

	err := datastore.GetAll(c, q, &results)
	if err != nil {
		return nil, err
	}

	if len(results) == 0 {
		return nil, fmt.Errorf("AlertsJSON for Tree \"%s\" not found", tree)
	}

	return results[0], nil
}
