package analyzer

import (
	"cloud.google.com/go/bigquery"
	"fmt"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
	"google.golang.org/api/iterator"
	"infra/appengine/sheriff-o-matic/som/analyzer/step"
	"infra/monitoring/messages"
	"sort"
	"strings"
	"time"
)

const selectFromWhere = `
SELECT
  Project,
  Bucket,
  Builder,
  MasterName,
  StepName,
  TestNamesFingerprint,
  TestNamesTrunc,
  NumTests,
  BuildIdBegin,
  BuildIdEnd,
  CPRangeOutputBegin,
  CPRangeOutputEnd,
  CPRangeInputBegin,
  CPRangeInputEnd,
  CulpritIdRangeBegin,
  CulpritIdRangeEnd,
  StartTime
FROM
	` + "`%s.%s.sheriffable_failures`" + `
WHERE
`

// TODO: customize the WHERE clause for chromium.  I suspect
// just using the project field isn't quite right.
const failuresQuery = selectFromWhere + `
	(Project = %q OR MasterName = %q)
	AND Bucket NOT IN ("try", "cq", "staging", "general")
    AND (Mastername IS NULL
		OR Mastername NOT LIKE "%%.fyi")
	AND Builder NOT LIKE "%%bisect%%"
LIMIT
	1000
`

const androidFailuresQuery = selectFromWhere + `
MasterName IN ("internal.client.clank",
    "internal.client.clank_tot",
    "chromium.android")
  OR (MasterName = "chromium"
    AND builder="Android")
  OR (MasterName = "chromium.webkit"
    AND builder IN ("Android Builder",
	  "Webkit Android (Nexus4)"))
  OR (MasterName = "official.chrome"
	AND builder IN (
		"android-arm-official-tests",
		"android-arm64-official-tests",
		"android-arm-beta-tests",
		"android-arm64-beta-tests",
		"android-arm-stable-tests",
		"android-arm64-stable-tests"
		)
	)
  OR (MasterName = "official.chrome.continuous"
	AND builder IN (
		"android-arm-beta",
		"android-arm64-beta",
		"android-arm64-stable",
		"android-arm64-stable",
		"android-arm-stable"
		)
  	)
LIMIT
	1000
`

const chromiumGPUFYIFailuresQuery = selectFromWhere + `
  MasterName = "chromium.gpu.fyi"
`

const crosFailuresQuery = selectFromWhere + `
	project = "chromeos"
	AND bucket IN ("postsubmit", "annealing")
`

// This list of builders is from
// https://cs.chromium.org/chromium/build/scripts/slave/recipe_modules/gatekeeper/resources/gatekeeper_trees.json?l=44
const iosFailuresQuery = selectFromWhere + `
	project = "chromium"
	AND MasterName IN ("chromium.mac")
	AND builder IN (
		"ios-device",
		"ios-device-xcode-clang",
		"ios-simulator",
		"ios-simulator-full-configs",
		"ios-simulator-xcode-clang"
	)
`

type failureRow struct {
	TestNamesFingerprint bigquery.NullInt64
	TestNamesTrunc       bigquery.NullString
	NumTests             bigquery.NullInt64
	StepName             string
	MasterName           bigquery.NullString
	Builder              string
	Bucket               string
	Project              string
	BuildIDBegin         bigquery.NullInt64
	BuildIDEnd           bigquery.NullInt64
	CPRangeInputBegin    *GitCommit
	CPRangeInputEnd      *GitCommit
	CPRangeOutputBegin   *GitCommit
	CPRangeOutputEnd     *GitCommit
	CulpritIDRangeBegin  bigquery.NullInt64
	CulpritIDRangeEnd    bigquery.NullInt64
	StartTime            bigquery.NullTimestamp
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
	Name            string `json:"step"`
	kind            string
	severity        messages.Severity
	Tests           []step.TestWithResult `json:"tests"`
	NumFailingTests int64                 `json:"num_failing_tests"`
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
	prefix := fmt.Sprintf("%s failing", f.Step.Name)

	if b.NumFailingTests > 0 {
		prefix = fmt.Sprintf("%s (%d tests)", prefix, b.NumFailingTests)
	}

	if len(bses) == 1 {
		return fmt.Sprintf("%s on %s/%s", prefix, f.Master.Name(), f.Build.BuilderName)
	}

	return fmt.Sprintf("%s on multiple builders", prefix)
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
	queryStr := ""
	switch tree {
	case "android":
		queryStr = fmt.Sprintf(androidFailuresQuery, appID, "chromium")
		break
	case "chromium.gpu.fyi":
		queryStr = fmt.Sprintf(chromiumGPUFYIFailuresQuery, appID, "chromium")
		break
	case "chromeos":
		queryStr = fmt.Sprintf(crosFailuresQuery, appID, "chromeos")
		break
	case "ios":
		queryStr = fmt.Sprintf(iosFailuresQuery, appID, "chromium")
		break
	case "fuchsia":
		queryStr = fmt.Sprintf(failuresQuery, appID, "fuchsia", tree, tree)
		break
	default:
		queryStr = fmt.Sprintf(failuresQuery, appID, "chromium", tree, tree)
	}

	logging.Infof(ctx, "query: %s", queryStr)
	q := client.Query(queryStr)
	it, err := q.Read(ctx)
	if err != nil {
		return nil, err
	}
	return processBQResults(ctx, it)
}

type nexter interface {
	Next(interface{}) error
}

func processBQResults(ctx context.Context, it nexter) ([]messages.BuildFailure, error) {
	alertedBuildersByStep := map[string][]messages.AlertedBuilder{}
	alertedBuildersByStepAndTests := map[string]map[int64][]messages.AlertedBuilder{}
	testNamesTruncForFingerprint := map[int64]string{}

	for {
		var r failureRow
		err := it.Next(&r)
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, err
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
			FirstFailure:     r.BuildIDBegin.Int64,
			LatestFailure:    r.BuildIDEnd.Int64,
			URL:              fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s", r.Project, r.Bucket, r.Builder),
			LatestPassingRev: latestPassingRev,
			FirstFailingRev:  firstFailingRev,
			NumFailingTests:  r.NumTests.Int64,
		}

		forStep, ok := alertedBuildersByStep[r.StepName]
		if !ok {
			forStep = []messages.AlertedBuilder{}
			alertedBuildersByStep[r.StepName] = forStep
			alertedBuildersByStepAndTests[r.StepName] = map[int64][]messages.AlertedBuilder{}
		}
		forStep = append(forStep, ab)
		alertedBuildersByStep[r.StepName] = forStep
		if r.TestNamesFingerprint.Valid {
			testNamesTruncForFingerprint[r.TestNamesFingerprint.Int64] = r.TestNamesTrunc.StringVal

			forTest, ok := alertedBuildersByStepAndTests[r.StepName][r.TestNamesFingerprint.Int64]
			if !ok {
				forTest = []messages.AlertedBuilder{}
				alertedBuildersByStepAndTests[r.StepName][r.TestNamesFingerprint.Int64] = forTest
			}
			forTest = append(forTest, ab)
			alertedBuildersByStepAndTests[r.StepName][r.TestNamesFingerprint.Int64] = forTest
		}
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

		forTest, ok := alertedBuildersByStepAndTests[stepName]
		if ok && len(forTest) > 0 {
			for testNamesFingerprint, buildersForTest := range forTest {
				reason := &bqFailure{
					Name:     stepName, // TODO: Use step package's GetTestSuite here.
					kind:     "test",
					severity: messages.ReliableFailure,
				}
				testNames := strings.Split(testNamesTruncForFingerprint[testNamesFingerprint], "\n")
				sort.Strings(testNames)
				for _, testName := range testNames {
					reason.Tests = append(reason.Tests, step.TestWithResult{
						TestName: testName,
						// TODO: set these, as they are in test_step.go:
						// IsFlaky
						// SuspectedCLs
						// Expectations
						// Artifacts
					})
				}
				for _, abForTest := range buildersForTest {
					reason.NumFailingTests = abForTest.NumFailingTests
				}
				bf := messages.BuildFailure{
					StepAtFault: &messages.BuildStep{
						Step: &messages.Step{
							Name: stepName,
						},
					},
					Builders: buildersForTest,
					Reason: &messages.Reason{
						Raw: reason,
					},
					RegressionRanges: regressionRanges,
				}
				ret = append(ret, bf)
			}
		} else {
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
