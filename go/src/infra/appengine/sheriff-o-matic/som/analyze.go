package som

import (
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/analyzer"
	"infra/monitoring/client"
	"infra/monitoring/messages"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	tq "github.com/luci/gae/service/taskqueue"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"
)

const (
	logdiffQueue = "logdiff"
)

var (
	alertCount = metric.NewInt("sheriff_o_matic/analyzer/alert_count",
		"Number of alerts generated.",
		nil,
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

	alertCount.Set(c, int64(len(alerts)), tree)
	logging.Debugf(c, "storing %d alerts for %s", len(alerts), tree)

	if err := storeAlertsSummary(c, a, tree, &messages.AlertsSummary{
		RevisionSummaries: map[string]messages.RevisionSummary{},
		Alerts:            alerts,
	}); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
	}
	if tree == "chromium" {
		if err := enqueueLogDiffTask(c, alerts); err != nil {
			errStatus(c, w, http.StatusInternalServerError, err.Error())
		}
	}
	w.Write([]byte("ok"))
}

func enqueueLogDiffTask(ctx context.Context, alerts []messages.Alert) error {
	for _, alert := range alerts {
		if bf, ok := alert.Extension.(messages.BuildFailure); ok {
			for _, builder := range bf.Builders {
				buildNum2 := builder.LatestPassing
				buildNum1 := builder.LatestFailure
				master := builder.Master
				// This is checking if there's redundant data in datastore already
				var diffs []*LogDiff
				q := datastore.NewQuery("LogDiff")
				q = q.Eq("Master", master).Eq("Builder", builder.Name).Eq("BuildNum1", buildNum1).Eq("BuildNum2", buildNum2)
				err := datastore.GetAll(ctx, q, &diffs)
				if err != nil {
					logging.Errorf(ctx, "err with getting data from datastore: %v", err)
				}
				if len(diffs) != 0 {
					continue
				}
				err = datastore.RunInTransaction(ctx, func(ctx context.Context) error {
					data := &LogDiff{nil, master, builder.Name, buildNum1, buildNum2, "", false}
					if err := datastore.AllocateIDs(ctx, data); err != nil {
						logging.Errorf(ctx, "error allocating id: %v", err)
						return err
					}
					values := url.Values{}
					values.Set("lastFail", strconv.Itoa(int(buildNum1)))
					values.Set("lastPass", strconv.Itoa(int(buildNum2)))
					values.Set("master", master)
					values.Set("builder", builder.Name)
					values.Set("ID", data.ID)
					if err := datastore.Put(ctx, data); err != nil {
						logging.Errorf(ctx, "storing data: %v", err)
						return err
					}
					t := tq.NewPOSTTask("/_ah/queue/logdiff", values)

					workerHost, err := info.ModuleHostname(ctx, "analyzer", "", "")
					if err != nil {
						logging.Errorf(ctx, "err routing worker to analyzer: %v", err)
						return err
					}
					t.Header["HOST"] = []string{workerHost}

					if err := tq.Add(ctx, logdiffQueue, t); err != nil {
						logging.Errorf(ctx, "error enqueuing task: %v", err)
						return err
					}
					return nil
				}, nil)
				if err != nil {
					return err
				}
			}
		}
	}
	return nil
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
