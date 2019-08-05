package analyzer

import (
	"cloud.google.com/go/bigquery"
	"fmt"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
	"google.golang.org/api/iterator"
	"infra/monitoring/messages"
	"sort"
	"strings"
	"time"
)

// TODO: customize the WHERE clause for chromium.  I suspect
// just using the project field isn't quite right.
const failuresQuery = `
SELECT
  Project,
  Bucket,
  Builder,
  MasterName,
  StepName,
  BuildRangeBegin,
  BuildRangeEnd,
  CPRangeOutputBegin,
  CPRangeOutputEnd,
  CPRangeInputBegin,
  CPRangeInputEnd,
  StartTime
FROM
	` + "`%s.events.sheriffable_failures`" + `
WHERE
	project = %q
  AND bucket NOT IN ("try",
    "cq",
    "staging",
    "general")
  AND (mastername IS NULL
		OR mastername NOT LIKE "%%.fyi")
	AND builder not like "%%bisect%%"
LIMIT
	1000
`

const androidFailuresQuery = `
SELECT
  Project,
  Bucket,
  Builder,
  MasterName,
  StepName,
  BuildRangeBegin,
  BuildRangeEnd,
  CPRangeOutputBegin,
  CPRangeOutputEnd,
  CPRangeInputBegin,
  CPRangeInputEnd,
	StartTime
FROM
	` + "`%s.events.sheriffable_failures`" + `
WHERE
MasterName IN ("internal.client.clank",
    "internal.client.clank_tot",
    "chromium.android")
  OR (MasterName = "chromium"
    AND builder="Android")
  OR (MasterName = "chromium.webkit"
    AND builder IN ("Android Builder",
      "Webkit Android (Nexus4)"))
LIMIT
	1000
`

type failureRow struct {
	StepName           string
	MasterName         bigquery.NullString
	Builder            string
	Bucket             string
	Project            string
	BuildRangeBegin    bigquery.NullInt64
	BuildRangeEnd      bigquery.NullInt64
	CPRangeInputBegin  *GitCommit
	CPRangeInputEnd    *GitCommit
	CPRangeOutputBegin *GitCommit
	CPRangeOutputEnd   *GitCommit
	StartTime          bigquery.NullTimestamp
}

// GitCommit represents a struct column for BQ query results.
type GitCommit struct {
	Project  bigquery.NullString
	Ref      bigquery.NullString
	Host     bigquery.NullString
	ID       bigquery.NullString
	Position bigquery.NullInt64
}

// This type is a catch-all for every kind of failure. In a better,
// simpler design we wouldn't have to use this but it's here to make
// the transition from previous analyzer logic easier.
type bqFailure struct {
	Name     string `json:"name"`
	kind     string
	severity messages.Severity
}

func (b *bqFailure) Signature() string {
	return b.Name
}

func (b *bqFailure) Kind() string {
	return b.kind
}

func (b *bqFailure) Severity() messages.Severity {
	return b.severity
}

func (b *bqFailure) Title(bses []*messages.BuildStep) string {
	f := bses[0]
	if len(bses) == 1 {
		return fmt.Sprintf("%s failing on %s/%s", f.Step.Name, f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("%s failing on multiple builders", f.Step.Name)
}

// GetBigQueryAlerts generates alerts for currently failing build steps, using
// BigQuery to do most of the heavy lifting.
// Note that this returns alerts for all failing steps, so filtering should
// be applied on the return value.
// TODO: Some post-bq result merging with heuristics:
//   - Merge alerts for sets of multiple failing steps. Currently will return one alert
//     for each failing step on a builder. If step_a and step_b are failing on the same
//     builder or set of builders, they should be merged into a single alert.
func GetBigQueryAlerts(ctx context.Context, tree string) ([]messages.BuildFailure, error) {
	appID := info.AppID(ctx)
	if appID == "None" {
		appID = "sheriff-o-matic-staging"
	}
	ctx, _ = context.WithTimeout(ctx, 10*time.Minute)
	client, err := bigquery.NewClient(ctx, appID)
	if err != nil {
		return nil, err
	}
	queryStr := fmt.Sprintf(failuresQuery, appID, tree)
	if tree == "android" {
		queryStr = fmt.Sprintf(androidFailuresQuery, appID)
	}
	logging.Infof(ctx, "query: %q", queryStr)
	q := client.Query(queryStr)
	it, err := q.Read(ctx)
	if err != nil {
		return nil, err
	}

	alertedBuildersByStep := map[string][]messages.AlertedBuilder{}
	for {
		var r failureRow
		err := it.Next(&r)
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
		}
		// TODO: figure out how to better handle build steps that
		// have never passed, ever.
		if r.BuildRangeBegin.Int64 == 0 {
			continue
		}
		gitBegin := r.CPRangeOutputBegin
		if gitBegin == nil {
			gitBegin = r.CPRangeInputBegin
		}
		gitEnd := r.CPRangeOutputEnd
		if gitEnd == nil {
			gitEnd = r.CPRangeInputEnd
		}
		var latestPassingRev, firstFailingRev *messages.RevisionSummary
		if gitBegin != nil {
			latestPassingRev = &messages.RevisionSummary{
				Position: int(gitBegin.Position.Int64),
				Branch:   gitBegin.Ref.StringVal,
				Host:     gitBegin.Host.StringVal,
				Repo:     gitBegin.Project.StringVal,
				GitHash:  gitBegin.ID.StringVal,
			}
		}
		if gitEnd != nil {
			firstFailingRev = &messages.RevisionSummary{
				Position: int(gitEnd.Position.Int64),
				Branch:   gitEnd.Ref.StringVal,
				Host:     gitEnd.Host.StringVal,
				Repo:     gitEnd.Project.StringVal,
				GitHash:  gitEnd.ID.StringVal,
			}
		}
		ab := messages.AlertedBuilder{
			Project:          r.Project,
			Bucket:           r.Bucket,
			Name:             r.Builder,
			Master:           r.MasterName.StringVal,
			FirstFailure:     r.BuildRangeBegin.Int64,
			LatestFailure:    r.BuildRangeEnd.Int64,
			URL:              fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s", r.Project, r.Bucket, r.Builder),
			LatestPassingRev: latestPassingRev,
			FirstFailingRev:  firstFailingRev,
		}
		forStep, ok := alertedBuildersByStep[r.StepName]
		if !ok {
			forStep = []messages.AlertedBuilder{}
			alertedBuildersByStep[r.StepName] = forStep
		}
		forStep = append(forStep, ab)
		alertedBuildersByStep[r.StepName] = forStep
	}

	ret := []messages.BuildFailure{}
	for stepName, alertedBuilders := range alertedBuildersByStep {
		alertedBuilders := alertedBuilders
		// While we have the alertedBuilders for this alert, we should identify the
		// narrowest range of commit posistions implicated.
		var earliestRev, latestRev *messages.RevisionSummary
		for _, alertedBuilder := range alertedBuilders {
			if earliestRev == nil || alertedBuilder.LatestPassingRev != nil && alertedBuilder.LatestPassingRev.Position > 0 && alertedBuilder.LatestPassingRev.Position > earliestRev.Position {
				earliestRev = alertedBuilder.LatestPassingRev
			}
			if latestRev == nil || alertedBuilder.FirstFailingRev != nil && alertedBuilder.FirstFailingRev.Position > 0 && alertedBuilder.FirstFailingRev.Position < latestRev.Position {
				latestRev = alertedBuilder.FirstFailingRev
			}
		}

		// TODO: update commitPosFromOutputProperties to get positions for repos besides
		// chromium. There is some uncertainty that build.Output.Properties will have this
		// information in all cases for all trees, since its contents is determined by
		// whatever is in the recipes.
		regressionRanges := []*messages.RegressionRange{}
		if latestRev != nil && earliestRev != nil {
			regRange := &messages.RegressionRange{
				Repo: earliestRev.Repo,
				Host: earliestRev.Host,
			}
			if earliestRev.GitHash != "" && latestRev.GitHash != "" {
				regRange.Revisions = []string{earliestRev.GitHash, latestRev.GitHash}
			}
			if earliestRev.Position != 0 && latestRev.Position != 0 {
				regRange.Positions = []string{
					fmt.Sprintf("%s@{#%d}", earliestRev.Branch, earliestRev.Position),
					fmt.Sprintf("%s@{#%d}", latestRev.Branch, latestRev.Position),
				}
			}
			regressionRanges = append(regressionRanges, regRange)
		}

		reason := &bqFailure{
			Name:     stepName,
			kind:     "basic",
			severity: messages.ReliableFailure,
		}

		bf := messages.BuildFailure{
			StepAtFault: &messages.BuildStep{
				Step: &messages.Step{
					Name: stepName,
				},
			},
			Builders: alertedBuilders,
			Reason: &messages.Reason{
				Raw: reason,
			},
			RegressionRanges: regressionRanges,
		}
		ret = append(ret, bf)
	}

	ret = filterHierarchicalSteps(ret)
	return ret, nil
}

func builderKey(b messages.AlertedBuilder) string {
	return fmt.Sprintf("%s/%s/%s", b.Project, b.Bucket, b.Name)
}

func filterHierarchicalSteps(failures []messages.BuildFailure) []messages.BuildFailure {
	ret := []messages.BuildFailure{}
	// First group failures by builder.
	failuresByBuilder := map[string][]messages.BuildFailure{}
	builders := map[string]messages.AlertedBuilder{}
	for _, f := range failures {
		for _, b := range f.Builders {
			key := builderKey(b)
			builders[key] = b
			if _, ok := failuresByBuilder[key]; !ok {
				failuresByBuilder[key] = []messages.BuildFailure{}
			}
			failuresByBuilder[key] = append(failuresByBuilder[key], f)
		}
	}

	filteredFailuresByBuilder := map[string]stringset.Set{}

	// For each builder, sort failing steps.
	for key, failures := range failuresByBuilder {
		sort.Sort(byStepName(failures))
		filteredFailures := stringset.New(0)
		// For each step in builder steps, if it's a prefix of the one after it,
		// ignore that step.
		for i, step := range failures {
			if i <= len(failures)-2 {
				nextStep := failures[i+1]
				if strings.HasPrefix(nextStep.StepAtFault.Step.Name, step.StepAtFault.Step.Name+"|") {
					// Skip this step since it has at least one child.
					continue
				}
			}
			filteredFailures.Add(step.StepAtFault.Step.Name)
		}
		filteredFailuresByBuilder[key] = filteredFailures
	}

	// Now filter out BuildFailures whose StepAtFault has been filtered out for
	// that builder.
	for _, failure := range failures {
		filteredBuilders := []messages.AlertedBuilder{}
		for _, b := range failure.Builders {
			key := builderKey(b)
			filtered := filteredFailuresByBuilder[key]
			if filtered.Has(failure.StepAtFault.Step.Name) {
				filteredBuilders = append(filteredBuilders, b)
			}
		}
		if len(filteredBuilders) > 0 {
			failure.Builders = filteredBuilders
			ret = append(ret, failure)
		}
	}

	return ret
}

// TODO(seanmccullough): rename if we aren't sorting by step name, which may
// not be the most robust sorting method. Check if Step.Number is always
// populated, though that may not translate well because multiple builders are
// grouped by failing step and the same "step" may occur at different
// indexes in different builders.
type byStepName []messages.BuildFailure

func (a byStepName) Len() int      { return len(a) }
func (a byStepName) Swap(i, j int) { a[i], a[j] = a[j], a[i] }
func (a byStepName) Less(i, j int) bool {
	return a[i].StepAtFault.Step.Name < a[j].StepAtFault.Step.Name
}
