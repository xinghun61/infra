package handler

import (
	"crypto/sha1"
	"fmt"
	"net/http"
	"net/url"
	"sort"
	"sync"
	"time"

	"github.com/golang/protobuf/ptypes"
	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"infra/appengine/sheriff-o-matic/som/analyzer"
	buildstep "infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/model"
	"infra/appengine/sheriff-o-matic/som/model/gen"
	"infra/monitoring/messages"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/bq"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/server/router"

	"cloud.google.com/go/bigquery"
)

const (
	logdiffQueue = "logdiff"

	// groupingPoolSize controls the number of goroutines used to creating
	// groupings when post processing the generated alerts. Has not been tuned.
	groupingPoolSize = 2

	bqDatasetID = "events"
	bqTableID   = "alerts"
)

var (
	alertCount = metric.NewInt("sheriff_o_matic/analyzer/alert_count",
		"Number of alerts generated.",
		nil,
		field.String("tree"),
		field.String("category")) // "consistent", "new" etc

	alertGroupCount = metric.NewInt("sheriff_o_matic/analyzer/alert_group_count",
		"Number of alert groups active.",
		nil,
		field.String("tree"),
		field.String("category")) // "consistent", "new" etc
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

type ctxKeyType string

var analyzerCtxKey = ctxKeyType("analyzer")

// WithAnalyzer returns a context with a attached as a context value.
func WithAnalyzer(ctx context.Context, a *analyzer.Analyzer) context.Context {
	return context.WithValue(ctx, analyzerCtxKey, a)
}

// GetAnalyzeHandler enqueues a request to run an analysis on a particular tree.
// This is usually hit by appengine cron rather than manually.
func GetAnalyzeHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	tree := p.ByName("tree")
	a, ok := c.Value(analyzerCtxKey).(*analyzer.Analyzer)
	if !ok {
		errStatus(c, w, http.StatusInternalServerError, "no analyzer set in Context")
		return
	}
	source := r.FormValue("use")
	var alertsSummary *messages.AlertsSummary
	var err error

	// TODO: remove this check once we're off buildbot.
	if source == "bigquery" {
		c = appengine.WithContext(c, r)
		alertsSummary, err = generateBigQueryAlerts(c, a, tree)
	} else {
		alertsSummary, err = generateAlerts(ctx, a)
	}

	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	alertsSummary.Timestamp = messages.TimeToEpochTime(time.Now())
	if err := putAlertsBigQuery(c, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error sending alerts to bigquery: %v", err)
		// Not fatal, just log and continue.
	}

	w.Write([]byte("ok"))
}

func generateBigQueryAlerts(c context.Context, a *analyzer.Analyzer, tree string) (*messages.AlertsSummary, error) {
	gkRules, err := getGatekeeperRules(c)
	if err != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err)
		return nil, err
	}

	builderAlerts, err := analyzer.GetBigQueryAlerts(c, tree)
	if err != nil {
		return nil, err
	}

	// Filter out ignored builders/steps.
	filteredBuilderAlerts := []messages.BuildFailure{}
	for _, ba := range builderAlerts {
		builders := []messages.AlertedBuilder{}
		for _, b := range ba.Builders {
			masterURL, err := url.Parse(fmt.Sprintf("https://build.chromium.org/p/%s", b.Master))
			if err != nil {
				return nil, err
			}
			master := &messages.MasterLocation{
				URL: *masterURL,
			}

			if !gkRules.ExcludeFailure(c, tree, master, b.Name, ba.StepAtFault.Step.Name) {
				builders = append(builders, b)
			}
		}
		if len(builders) > 0 {
			ba.Builders = builders
			filteredBuilderAlerts = append(filteredBuilderAlerts, ba)
		}
	}
	logging.Infof(c, "filtered alerts, before: %d after: %d", len(builderAlerts), len(filteredBuilderAlerts))
	builderAlerts = attachFindItResults(c, filteredBuilderAlerts, a.FindIt)

	alerts := []messages.Alert{}
	for _, ba := range builderAlerts {
		title := fmt.Sprintf("Step %q failing on %d builder(s)", ba.StepAtFault.Step.Name, len(ba.Builders))
		startTime := messages.TimeToEpochTime(time.Now())
		severity := messages.NewFailure
		for _, b := range ba.Builders {
			if b.StartTime > 0 && b.StartTime < startTime {
				startTime = b.StartTime
			}
			if b.LatestFailure-b.FirstFailure != 0 {
				severity = messages.ReliableFailure
			}
		}

		alert := messages.Alert{
			Key:       fmt.Sprintf("%s.%v", tree, ba.Reason.Signature()),
			Title:     title,
			Extension: ba,
			StartTime: startTime,
			Severity:  severity,
		}

		switch ba.Reason.Kind() {
		case "test":
			alert.Type = messages.AlertTestFailure
		default:
			alert.Type = messages.AlertBuildFailure
		}

		alerts = append(alerts, alert)
	}

	logging.Infof(c, "%d alerts generated for tree %q", len(alerts), tree)

	alertsSummary := &messages.AlertsSummary{
		Timestamp:         messages.TimeToEpochTime(time.Now()),
		RevisionSummaries: map[string]messages.RevisionSummary{},
		Alerts:            alerts,
	}

	if err := storeAlertsSummary(c, a, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		return nil, err
	}

	return alertsSummary, nil
}

func attachFindItResults(ctx context.Context, failures []messages.BuildFailure, finditClient client.FindIt) []messages.BuildFailure {
	for _, bf := range failures {
		stepName := bf.StepAtFault.Step.Name
		for _, someBuilder := range bf.Builders {
			buildAlternativeID := messages.BuildIdentifierByNumber{
				Project: someBuilder.Project,
				Bucket:  someBuilder.Bucket,
				Builder: someBuilder.Name,
				Number:  someBuilder.LatestFailure,
			}
			results, err := finditClient.FinditBuildbucket(ctx, &buildAlternativeID, []string{stepName})
			if err != nil {
				logging.Errorf(ctx, "error getting findit results: %v", err)
			}

			for _, result := range results {
				if result.StepName != bf.StepAtFault.Step.Name {
					continue
				}

				bf.Culprits = append(bf.Culprits, result.Culprits...)
				bf.HasFindings = len(result.Culprits) > 0
				bf.IsFinished = result.IsFinished
				bf.IsSupported = result.IsSupported
			}
		}
	}
	return failures
}

func generateAlerts(ctx *router.Context, a *analyzer.Analyzer) (*messages.AlertsSummary, error) {
	c, w, p := ctx.Context, ctx.Writer, ctx.Params

	tree := p.ByName("tree")

	gkRules, err := getGatekeeperRules(c)
	if err != nil {
		logging.Errorf(c, "error getting gatekeeper rules: %v", err)
		return nil, err
	}

	trees, err := getGatekeeperTrees(c)
	if err != nil {
		logging.Errorf(c, fmt.Sprintf("getting gatekeeper trees: %v", err))
		return nil, err
	}

	treeCfgs, ok := trees[tree]
	if !ok {
		errStatus(c, w, http.StatusNotFound, fmt.Sprintf("unrecognized tree: %s", tree))
		return nil, nil
	}

	a.Gatekeeper = gkRules

	alerts := []messages.Alert{}
	groupByCat := map[string]map[string]int{}

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
				buildExtract, err := a.Milo.BuildExtract(c, &masterLoc)
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
			// Some errors are tolerated so long as some analysis succeeded.
			logging.Errorf(c, "error creating alerts: %v", anyErr)
		}

		groupsByCategory, err := mergeAlertsByReason(ctx, alerts)
		if err != nil {
			logging.Errorf(c, "error merging alerts by reason: %v", err)
			return nil, err
		}
		for cat, groups := range groupsByCategory {
			if _, ok := groupByCat[cat]; !ok {
				groupByCat[cat] = map[string]int{}
			}
			for gID := range groups {
				groupByCat[cat][gID]++
			}
		}
	}

	// Update raw alert counts by category monitoring metrics.
	alertCountByCategory := map[string]int{}
	for _, a := range alerts {
		cat := alertCategory(&a)
		alertCountByCategory[cat]++
	}

	for cat, count := range alertCountByCategory {
		alertCount.Set(c, int64(count), tree, cat)
	}

	// Update alert groups counts by category monitoring metrics.
	for cat, groups := range groupByCat {
		alertGroupCount.Set(c, int64(len(groups)), tree, cat)
	}

	// Attach test result histories to test failure alerts.
	for _, alert := range alerts {
		if !isTestFailure(alert) {
			continue
		}
		if err := attachTestResults(c, &alert, a.TestResults); err != nil {
			logging.WithError(err).Errorf(c, "attaching results")
		}
	}

	logging.Debugf(c, "storing %d alerts for %s", len(alerts), tree)
	alertsSummary := &messages.AlertsSummary{
		RevisionSummaries: map[string]messages.RevisionSummary{},
		Alerts:            alerts,
	}

	if err := storeAlertsSummary(c, a, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		return nil, err
	}

	return alertsSummary, nil
}

func alertCategory(a *messages.Alert) string {
	cat := "other"
	if a.Severity == messages.NewFailure {
		cat = "new"
	} else if a.Severity == messages.ReliableFailure {
		cat = "consistent"
	}
	return cat
}

func attachTestResults(c context.Context, alert *messages.Alert, trc client.TestResults) error {
	bf, ok := alert.Extension.(messages.BuildFailure)
	if !ok {
		return fmt.Errorf("couldn't cast to a BuildFailure: %+v", bf)
	}
	step := bf.StepAtFault.Step.Name
	tf, ok := bf.Reason.Raw.(*buildstep.TestFailure)
	if !ok {
		return fmt.Errorf("couldn't cast to a TestFailure: %+v", tf)
	}

	// TODO(seanmccullough) use all TestNames, not just the last one.
	test := ""
	for _, t := range tf.TestNames {
		test = t
	}

	resultsByMaster := map[string]*messages.MasterResults{}
	alertTestResults := messages.AlertTestResults{
		TestName:      test,
		MasterResults: []messages.MasterResults{},
	}

	for _, builder := range bf.Builders {
		masterName := builder.Master
		builderName := builder.Name
		trh, err := trc.GetTestResultHistory(c, masterName, builderName, step)
		if err != nil {
			logging.WithError(err).Errorf(c, "couldn't get test results history for %q %q %q %q", test, masterName, builderName, step)
			continue
		}

		// Go back one build before LatestPassing for extra history, try to get
		// the last 10 builds if possible.
		end := builder.LatestPassing - 1
		if builder.LatestFailure > 11 && builder.LatestFailure-builder.LatestPassing < 10 {
			end = builder.LatestFailure - 11
		}

		for _, test := range tf.TestNames {
			tr, err := trh.ResultsForBuildRange(test, builder.LatestFailure, end)
			if err != nil {
				logging.Errorf(c, err.Error())
				logging.WithError(err).Errorf(c, "couldn't get test results history for %q %q %q %q in build range [%d, %d]", test, masterName, builderName, step, builder.LatestPassing, builder.LatestFailure)
				continue
			}
			if _, ok := resultsByMaster[masterName]; !ok {
				resultsByMaster[masterName] = &messages.MasterResults{
					MasterName:     masterName,
					BuilderResults: []messages.BuilderResults{},
				}
			}
			masterResults := resultsByMaster[masterName]
			builderResults := messages.BuilderResults{
				BuilderName: builderName,
				Results:     []messages.Results{},
			}

			// Now attach to bf.Reason.Raw (which should be step.TestFailure,
			// which has AlertTestResults []messages.AlertTestResults
			for _, r := range tr {
				builderResults.Results = append(builderResults.Results,
					messages.Results{
						BuildNumber: r.BuildNumber,
						Revision:    r.ChromeRevision,
						Actual:      r.Results,
					})
			}
			masterResults.BuilderResults = append(masterResults.BuilderResults, builderResults)
		}
	}
	for _, masterResult := range resultsByMaster {
		alertTestResults.MasterResults = append(alertTestResults.MasterResults, *masterResult)
	}
	tf.AlertTestResults = append(tf.AlertTestResults, alertTestResults)
	bf.Reason.Raw = tf

	return nil
}

// groupCounts maps alert category to a map of group IDs to counts of alerts
// in that category and group.
type groupCounts map[string]map[string]int

// mergeAlertsByReason merges alerts for step failures occurring across multiple builders into
// one alert with multiple builders indicated.
// FIXME: Move the regression range logic into package regrange
// This logic is for buildbot alerts, not buildbucket alerts.
func mergeAlertsByReason(ctx *router.Context, alerts []messages.Alert) (groupCounts, error) {
	c, p := ctx.Context, ctx.Params

	tree := p.ByName("tree")

	byReason := map[string][]messages.Alert{}
	for _, alert := range alerts {
		bf, ok := alert.Extension.(messages.BuildFailure)
		if !ok {
			logging.Infof(c, "%s failed, but isn't a builder-failure: %s", alert.Key, alert.Type)
			continue
		}
		r := bf.Reason
		k := r.Kind() + "|" + r.Signature()
		byReason[k] = append(byReason[k], alert)
	}

	sortedReasons := []string{}
	for reason := range byReason {
		sortedReasons = append(sortedReasons, reason)
	}

	sort.Strings(sortedReasons)

	// Maps alert category to map of groupID to count of alerts in group.
	groupIDs := groupCounts{}
	var mux sync.Mutex

	err := parallel.WorkPool(groupingPoolSize, func(workC chan<- func() error) {
		for _, reason := range sortedReasons {
			stepAlerts := byReason[reason]
			if len(stepAlerts) == 1 {
				continue
			}

			workC <- func() error {
				sort.Sort(messages.Alerts(stepAlerts))
				mergedBF := stepAlerts[0].Extension.(messages.BuildFailure)

				stepsAtFault := make([]*messages.BuildStep, len(stepAlerts))
				for i := range stepAlerts {
					bf, ok := stepAlerts[i].Extension.(messages.BuildFailure)
					if !ok {
						return fmt.Errorf("alert extension %s was not a BuildFailure", stepAlerts[i].Extension)
					}

					stepsAtFault[i] = bf.StepAtFault
				}

				groupTitle := mergedBF.Reason.Title(stepsAtFault)
				for _, alr := range stepAlerts {
					ann := &model.Annotation{
						Tree:      datastore.MakeKey(c, "Tree", tree),
						KeyDigest: fmt.Sprintf("%x", sha1.Sum([]byte(alr.Key))),
						Key:       alr.Key,
					}
					err := datastore.Get(c, ann)
					if err != nil && err != datastore.ErrNoSuchEntity {
						logging.Warningf(c, "got err while getting annotation from key %s: %s. Ignoring", alr.Key, err)
					}

					cat := alertCategory(&alr)

					// Count ungrouped alerts as their own groups.
					gID := groupTitle
					if ann != nil {
						gID = ann.GroupID
					}

					mux.Lock()
					if _, ok := groupIDs[cat]; !ok {
						groupIDs[cat] = map[string]int{}
					}
					groupIDs[cat][gID]++
					mux.Unlock()

					// If we didn't find an annotation, then the default group ID will be present.
					// We only want the case where the user explicitly sets the group to something.
					// Ungrouping an alert sets the group ID to "".
					if err != datastore.ErrNoSuchEntity && ann.GroupID != groupTitle {
						logging.Warningf(c, "Found groupID %s, wanted to set %s. Assuming user set group manually.", ann.GroupID, groupTitle)
						continue
					}

					ann.GroupID = groupTitle
					if err := datastore.Put(c, ann); err != nil {
						return fmt.Errorf("got err while put: %s", err)
					}
				}
				return nil
			}
		}
	})

	return groupIDs, err
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

	return putAlertsDatastore(c, tree, alertsSummary, true)
}

func putAlertsBigQuery(c context.Context, tree string, alertsSummary *messages.AlertsSummary) error {
	client, err := bigquery.NewClient(c, info.AppID(c))
	if err != nil {
		return err
	}
	up := bq.NewUploader(c, client, bqDatasetID, bqTableID)
	up.SkipInvalidRows = true
	up.IgnoreUnknownValues = true

	ts, err := ptypes.TimestampProto(alertsSummary.Timestamp.Time())
	if err != nil {
		return err
	}

	row := &gen.SOMAlertsEvent{
		Timestamp: ts,
		Tree:      tree,
		RequestId: appengine.RequestID(c),
	}

	for _, a := range alertsSummary.Alerts {
		alertEvt := &gen.SOMAlertsEvent_Alert{
			Key:   a.Key,
			Title: a.Title,
			Body:  a.Body,
			Type:  alertEventType(a.Type),
		}

		if bf, ok := a.Extension.(messages.BuildFailure); ok {
			for _, builder := range bf.Builders {
				newBF := &gen.SOMAlertsEvent_Alert_BuildbotFailure{
					Master:        builder.Master,
					Builder:       builder.Name,
					Step:          bf.StepAtFault.Step.Name,
					FirstFailure:  builder.FirstFailure,
					LatestFailure: builder.LatestFailure,
					LatestPassing: builder.LatestPassing,
				}
				alertEvt.BuildbotFailures = append(alertEvt.BuildbotFailures, newBF)
			}
		}

		row.Alerts = append(row.Alerts, alertEvt)
	}

	return up.Put(c, row)
}

var (
	alertToEventType = map[messages.AlertType]gen.SOMAlertsEvent_Alert_AlertType{
		messages.AlertStaleMaster:    gen.SOMAlertsEvent_Alert_STALE_MASTER,
		messages.AlertHungBuilder:    gen.SOMAlertsEvent_Alert_HUNG_BUILDER,
		messages.AlertOfflineBuilder: gen.SOMAlertsEvent_Alert_OFFLINE_BUILDER,
		messages.AlertIdleBuilder:    gen.SOMAlertsEvent_Alert_IDLE_BUILDER,
		messages.AlertInfraFailure:   gen.SOMAlertsEvent_Alert_INFRA_FAILURE,
		messages.AlertBuildFailure:   gen.SOMAlertsEvent_Alert_BUILD_FAILURE,
		messages.AlertTestFailure:    gen.SOMAlertsEvent_Alert_TEST_FAILURE,
	}
)

func alertEventType(t messages.AlertType) gen.SOMAlertsEvent_Alert_AlertType {
	if val, ok := alertToEventType[t]; ok {
		return val
	}
	panic("unknown alert type: " + string(t))
}

// isTestFaillure returns true/false based on whether the given Alert is for BuildFailure.
func isTestFailure(alert messages.Alert) bool {
	if bf, ok := alert.Extension.(messages.BuildFailure); ok && bf.Reason.Kind() == "test" {
		return true
	}
	return false
}
