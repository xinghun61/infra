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

type bySeverity []*messages.Alert

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
	var alertsSummary *messages.AlertsSummary
	var err error
	c = appengine.WithContext(c, r)

	alertsSummary, err = generateBigQueryAlerts(c, a, tree)

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
	filteredBuilderAlerts := []*messages.BuildFailure{}
	for _, ba := range builderAlerts {
		builders := []*messages.AlertedBuilder{}
		for _, b := range ba.Builders {
			masterURL, err := url.Parse(fmt.Sprintf("https://build.chromium.org/p/%s", b.Master))
			if err != nil {
				return nil, err
			}
			master := &messages.MasterLocation{
				URL: *masterURL,
			}

			// The chromium.clang tree specifically wants all of the failures.
			// Some other trees, who also reference chromium.clang builders do *not* want all of them.
			// This extra tree == "chromium.clang" condition works around this shortcoming of the gatekeeper
			// tree config format.
			if tree == "chromium.clang" || !gkRules.ExcludeFailure(c, tree, master, b.Name, ba.StepAtFault.Step.Name) {
				builders = append(builders, b)
			}
		}
		if len(builders) > 0 {
			ba.Builders = builders
			filteredBuilderAlerts = append(filteredBuilderAlerts, ba)
		}
	}
	logging.Infof(c, "filtered alerts, before: %d after: %d", len(builderAlerts), len(filteredBuilderAlerts))
	attachFindItResults(c, filteredBuilderAlerts, a.FindIt)

	alerts := []*messages.Alert{}
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

		alert := &messages.Alert{
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
		RevisionSummaries: map[string]*messages.RevisionSummary{},
		Alerts:            alerts,
	}

	if err := storeAlertsSummary(c, a, tree, alertsSummary); err != nil {
		logging.Errorf(c, "error storing alerts: %v", err)
		return nil, err
	}

	return alertsSummary, nil
}

func attachFindItResults(ctx context.Context, failures []*messages.BuildFailure, finditClient client.FindIt) {
	for _, bf := range failures {
		stepName := bf.StepAtFault.Step.Name
		for _, someBuilder := range bf.Builders {
			results, err := finditClient.FinditBuildbucket(ctx, someBuilder.LatestFailure, []string{stepName})
			if err != nil {
				logging.Errorf(ctx, "error getting findit results: %v", err)
			}

			for _, result := range results {
				if result.StepName != bf.StepAtFault.Step.Name {
					continue
				}

				bf.Culprits = append(bf.Culprits, result.Culprits...)
				bf.HasFindings = bf.HasFindings || len(result.Culprits) > 0
				bf.IsFinished = bf.IsFinished || result.IsFinished
				bf.IsSupported = bf.IsSupported || result.IsSupported
			}
		}
	}
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

// groupCounts maps alert category to a map of group IDs to counts of alerts
// in that category and group.
type groupCounts map[string]map[string]int

// mergeAlertsByReason merges alerts for step failures occurring across multiple builders into
// one alert with multiple builders indicated.
// FIXME: Move the regression range logic into package regrange
// This logic is for buildbot alerts, not buildbucket alerts.
func mergeAlertsByReason(ctx *router.Context, alerts []*messages.Alert) (groupCounts, error) {
	c, p := ctx.Context, ctx.Params

	tree := p.ByName("tree")

	byReason := map[string][]*messages.Alert{}
	for _, alert := range alerts {
		bf, ok := alert.Extension.(*messages.BuildFailure)
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
				mergedBF := stepAlerts[0].Extension.(*messages.BuildFailure)

				stepsAtFault := make([]*messages.BuildStep, len(stepAlerts))
				for i := range stepAlerts {
					bf, ok := stepAlerts[i].Extension.(*messages.BuildFailure)
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

					cat := alertCategory(alr)

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
