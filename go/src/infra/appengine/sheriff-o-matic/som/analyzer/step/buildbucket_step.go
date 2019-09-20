package step

import (
	"fmt"
	"net/url"
	"sort"
	"strings"

	"infra/appengine/sheriff-o-matic/som/client"

	"golang.org/x/net/context"

	//"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/logging"

	"infra/monitoring/messages"

	bbpb "go.chromium.org/luci/buildbucket/proto"
)

// DefaultBuildBucketStepAnalyzers returns a set of default step analyzers.
func DefaultBuildBucketStepAnalyzers(testResults client.TestResults, logReader client.LogReader, findit client.FindIt) BuildBucketStepAnalyzers {
	return []BuildBucketStepAnalyzer{
		&testResultBuildBucketAnalyzer{testResultsClient: testResults, finditClient: findit},
		&compileBuildBucketAnalyzer{logReader: logReader},
		&basicBuildBucketAnalyzer{},
	}
}

// BuildBucketStepAnalyzer reasons about a BuildStep and produces a set of reasons for the
// failure.  Each item in the returned array, if not nil, is the most
// informative reason that we know for the given step.
// If the analyzer returns errors, the reasons provided by it are only
// considered invalid for the build steps which the analyzer had errors
// processing.
type BuildBucketStepAnalyzer interface {
	Analyze(ctx context.Context, failure *bbpb.Step, build *bbpb.Build) ([]messages.ReasonRaw, error)
}

// BuildBucketStepAnalyzers is an ordered list of StepAnalyzers.
type BuildBucketStepAnalyzers []BuildBucketStepAnalyzer

// ReasonsForFailure is the default reason finder for package step.
func (analyzers BuildBucketStepAnalyzers) ReasonsForFailure(ctx context.Context, failure *bbpb.Step, build *bbpb.Build) []messages.ReasonRaw {
	for _, fa := range analyzers {
		res, errs := fa.Analyze(ctx, failure, build)
		if errs != nil {
			logging.Errorf(ctx, "Got errors while analyzing with %#v: %s", fa, errs)
		}
		if len(res) != 0 {
			return res
		}
	}

	return nil
}

/** Basic failures, a catch-all for things we can't analyze in more detail */

type basicBuildBucketFailure struct {
	Name string `json:"name"`
}

func (b *basicBuildBucketFailure) Signature() string {
	return "buildbucket:" + b.Name
}

func (b *basicBuildBucketFailure) Kind() string {
	return "basic"
}

func (b *basicBuildBucketFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (b *basicBuildBucketFailure) Title(bses []*messages.BuildStep) string {
	return fmt.Sprintf("%s failing", b.Name)
}

type basicBuildBucketAnalyzer struct{}

func (b *basicBuildBucketAnalyzer) Analyze(ctx context.Context, f *bbpb.Step, build *bbpb.Build) ([]messages.ReasonRaw, error) {
	results := []messages.ReasonRaw{}

	results = append(results, &basicBuildBucketFailure{
		Name: f.Name,
	})

	return results, nil
}

/** Compilation failures are build steps that fail to build a binary. */

type compileBuildBucketFailure struct {
	FailureLines []string `json:"failure_lines"`
}

func (b *compileBuildBucketFailure) Signature() string {
	return fmt.Sprintf("buildbucket:%s", strings.Join(b.FailureLines, ","))
}

func (b *compileBuildBucketFailure) Kind() string {
	return "compile"
}

func (b *compileBuildBucketFailure) Severity() messages.Severity {
	return messages.NoSeverity
}

func (b *compileBuildBucketFailure) Title(bses []*messages.BuildStep) string {
	return fmt.Sprintf("%d compile step(s) failing", len(b.FailureLines))
}

type compileBuildBucketAnalyzer struct {
	logReader client.LogReader
}

func (b *compileBuildBucketAnalyzer) Analyze(ctx context.Context, f *bbpb.Step, build *bbpb.Build) ([]messages.ReasonRaw, error) {
	results := []messages.ReasonRaw{}
	if f.Name != "compile" {
		return results, nil
	}
	master, builder, err := masterAndBuilderFromInputProperties(build)
	if err != nil {
		return nil, err
	}

	stdio, err := b.logReader.StdioForStep(ctx, master, builder, f.Name, int64(build.Number))
	if err != nil {
		return nil, fmt.Errorf("Couldn't get stdio for %s.%s.%s: %v", master.Name(), builder, f.Name, err)
	}

	// '(?P<path>.*):(?P<line>\d+):(?P<column>\d+): error:'
	// FIXME: This logic is copied from reasons_splitter.py, which comes with a FIXME.
	// The heuristic here seems pretty weak/brittle.  I've anecdotally seen compile step
	// failures that do not match this filter.
	nextLineIsFailure := false
	failureLines := []string{}
	for _, l := range stdio {
		if !nextLineIsFailure {
			if strings.HasPrefix(l, "FAILED:") {
				nextLineIsFailure = true
			}
			continue
		}
		if compileErrRE.MatchString(l) {
			parts := compileErrRE.FindAllStringSubmatch(l, -1)
			if len(parts) > 0 {
				failureLines = append(failureLines, fmt.Sprintf("%s:%s", parts[0][1], parts[0][2]))
			}
		}
	}
	sorted := failureLines
	sort.Strings(sorted)

	results = append(results, &compileBuildBucketFailure{
		FailureLines: sorted,
	})

	return results, nil
}

/**
Test result failures. These capture one or more tests failing within an
individual step.
*/

type testResultBuildBucketAnalyzer struct {
	testResultsClient client.TestResults
	finditClient      client.FindIt
}

func (b *testResultBuildBucketAnalyzer) Analyze(ctx context.Context, f *bbpb.Step, build *bbpb.Build) ([]messages.ReasonRaw, error) {
	results := []messages.ReasonRaw{}
	s := strings.Split(f.Name, " ")
	// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
	// term before the space, if there is one.
	// This isn't a good design, it's just the way things grew organically over time.
	// TODO: clean up all data embedded in step names so it's properly structured,
	// delete all code that tries to parse them, and declare we will not ever parse
	// them ever again.
	if !(strings.HasSuffix(s[0], "tests") || strings.HasSuffix(s[0], "test_apk")) {
		logging.Debugf(ctx, "%s has no tests", f.Name)
		return results, nil
	}

	master, builderName, err := masterAndBuilderFromInputProperties(build)
	if err != nil {
		return nil, err
	}

	suiteName := suiteNameForBuildBucketStep(master, f.Name)
	testResults, err := b.testResultsClient.TestResults(ctx, master, builderName, suiteName, int64(build.Number))
	if err != nil {
		return nil, err
	}

	if testResults == nil {
		return results, nil
	}

	failedTests := unexpectedFailures(testResults)

	sort.Strings(failedTests)
	if len(failedTests) > maxFailedTests {
		logging.Errorf(ctx, "Too many failed tests (%d) to put in the resulting json.", len(failedTests))
		failedTests = append(failedTests[:maxFailedTests], tooManyFailuresText)
	}

	tests, err := b.finditResultsForTests(ctx, master, builderName, suiteName, int64(build.Number), failedTests)
	if err != nil {
		return nil, err
	}

	// At some point, this should probably return one failure struct for each failing
	// test. That way the analyzer can group builders by *individual* failing tests
	// rather than by failing test *steps*.
	results = append(results, &TestFailure{
		StepName:  suiteName,
		TestNames: failedTests,
		Tests:     tests,
	})

	return results, nil
}

func (b *testResultBuildBucketAnalyzer) finditResultsForTests(ctx context.Context, master *messages.MasterLocation, builderName, suiteName string, buildNumber int64, failedTests []string) ([]TestWithResult, error) {
	testsWithFinditResults := []TestWithResult{}
	for _, test := range failedTests {
		testResult := TestWithResult{
			TestName:     test,
			IsFlaky:      false,
			SuspectedCLs: nil,
		}
		testsWithFinditResults = append(testsWithFinditResults, testResult)
	}
	return testsWithFinditResults, nil
}

func suiteNameForBuildBucketStep(master *messages.MasterLocation, stepName string) string {
	testSuite := stepName
	s := strings.Split(stepName, " ")

	if master.Name() == "chromium.perf" {
		found := false
		/*
			TODO: Uncomment, figure out how to do this without downloading swarming
			summaries for every build.
			// If a step has a swarming.summary log, then we assume it's a test
			for _, b := range bs.Step.Logs {
				if len(b) > 1 && b[0] == "swarming.summary" {
					found = true
					break
				}
			}
		*/
		if !found {
			return ""
		}
	} else if !(strings.HasSuffix(s[0], "tests") || strings.HasSuffix(s[0], "test_apk")) {
		// Some test steps have names like "webkit_tests iOS(dbug)" so we look at the first
		// term before the space, if there is one.
		return testSuite
	}

	// Recipes add a suffix to steps of the OS that it's run on, when the test
	// is swarmed. The step name is formatted like this: "<task title> on <OS>".
	// Added in this code:
	// https://chromium.googlesource.com/chromium/tools/build/+/9ef66559727c320b3263d7e82fb3fcd1b6a3bd55/scripts/slave/recipe_modules/swarming/api.py#846
	if len(s) > 2 && s[1] == "on" {
		testSuite = s[0]
	}

	return testSuite
}

// This is a utility function to help transition from buildbot to buildbucket.
// Some APIs we depend on (logReader, testResultsClient) still expect to have
// masters passed to them. Thankfully, build input properties often include these
// values so we just try to get them from there.
func masterAndBuilderFromInputProperties(build *bbpb.Build) (*messages.MasterLocation, string, error) {
	// Whelp, we need to get some buildbucket data into test-results server, and it
	// isn't there yet. The current test-results api requires a Master, Builder and
	// BuildNumber, which aren't native to buildbucket. So we need to pull them from
	// build properties, where someone(?) has so graciously left them (for now?).
	if build.Input == nil || build.Input.Properties == nil {
		return nil, "", fmt.Errorf("build input and/or properties not set")
	}

	masterField, ok := build.Input.Properties.Fields["mastername"]
	if !ok {
		return nil, "", fmt.Errorf("mastername property not present in build input properties")
	}
	masterStr := masterField.GetStringValue()

	builderNameField, ok := build.Input.Properties.Fields["buildername"]
	if !ok {
		return nil, "", fmt.Errorf("buildername property not present in build input properties")
	}
	builderName := builderNameField.GetStringValue()

	masterURL, err := url.Parse("https://ci.chromium.org/buildbot/" + masterStr)
	if err != nil {
		return nil, "", err
	}
	master := &messages.MasterLocation{
		URL: *masterURL,
	}

	return master, builderName, nil
}
