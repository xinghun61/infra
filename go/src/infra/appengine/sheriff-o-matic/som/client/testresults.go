package client

import (
	"encoding/json"
	"fmt"
	"net/url"
	"sync"

	"infra/appengine/test-results/model"
	"infra/monitoring/messages"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
)

type testResults struct {
	simpleClient
	knownResults knownResults
	// Used to make sure we cache known results only once. Local to struct
	// so that tests will refresh the cache when desired.
	cacheOnce sync.Once
}

// A cache of the test results /builders endpoint. This endpoints returns JSON
// representing what tests the test results server knows about.
// format is master -> test -> list of builders
type knownResults map[string]map[string][]string

// TestResults fetches the results of a step failure's test run.
func (trc *testResults) TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	if err := trc.cacheKnownData(ctx); err != nil {
		return nil, err
	}
	// Check if the test results server knows about this master builder test tuple
	masterValues := trc.knownResults[master.Name()]
	if len(masterValues) == 0 {
		return nil, nil
	}

	testValues := masterValues[stepName]
	if len(testValues) == 0 {
		return nil, nil
	}

	if !contains(testValues, builderName) {
		return nil, nil
	}

	v := url.Values{}
	v.Add("name", "full_results.json")
	v.Add("master", master.Name())
	v.Add("builder", builderName)
	v.Add("buildnumber", fmt.Sprintf("%d", buildNumber))
	v.Add("testtype", stepName)

	URL := fmt.Sprintf("%s/testfile?%s", trc.Host, v.Encode())
	tr := &messages.TestResults{}

	if code, err := trc.getJSON(ctx, URL, tr); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching test results %s: %v", code, URL, err)
		return nil, err
	}

	return tr, nil
}

// WithTestResults registers a new test-results client pointed at host.
func WithTestResults(ctx context.Context, host string) context.Context {
	trc := &testResults{
		simpleClient: simpleClient{Host: host, Client: nil},
	}

	return context.WithValue(ctx, testResultsKey, trc)
}

// cacheKnownData caches known test results data from the given server.
func (trc *testResults) cacheKnownData(ctx context.Context) error {
	var errResult error
	trc.cacheOnce.Do(func() {
		// If we already have results, move on. Mostly used for testing.
		if trc.knownResults != nil {
			return
		}
		trc.knownResults = map[string]map[string][]string{}
		URL := fmt.Sprintf("%s/data/builders", trc.Host)
		tmpCache := &model.BuilderData{}
		code, err := trc.getJSON(ctx, URL, tmpCache)
		if err != nil {
			errResult = err
			return
		}
		if code > 400 {
			errResult = fmt.Errorf("test result cache request failed with code %v", code)
			return
		}

		for _, master := range tmpCache.Masters {
			trc.knownResults[master.Name] = map[string][]string{}
			for testName, test := range master.Tests {
				trc.knownResults[master.Name][testName] = test.Builders
			}
		}
	})
	return errResult
}

// GetTestResults returns the currently registered test-results client, or panics.
func GetTestResults(ctx context.Context) *testResults {
	ret, ok := ctx.Value(testResultsKey).(*testResults)
	if !ok {
		panic("No test-results client set in context")
	}
	return ret
}

// GetTestResultHistory returns the result history of a given test.
func (trc *testResults) GetTestResultHistory(ctx context.Context, master, builderName, stepName string) (*BuilderTestHistory, error) {
	v := url.Values{}
	v.Add("master", master)
	v.Add("builder", builderName)
	v.Add("testtype", stepName)
	v.Add("name", "results-small.json")

	URL := fmt.Sprintf("%s/testfile?%s", trc.Host, v.Encode())

	// This is ugly and inefficient, but it deals with how results-small.json
	// has a top-level "version" property mixed in with a map of string to results structs.
	res := map[string]interface{}{}
	if code, err := trc.getJSON(ctx, URL, &res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching test run history %s: %v", code, URL, err)
		return nil, err
	}
	delete(res, "version")
	br := map[string]*BuilderTestHistory{}
	data, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(data, &br)
	return br[builderName], err
}

// BuilderTestHistory contains data about the history of tests run on a builder.
// Its structure is reverse-engineered from what I could find in the data
// fetched by the flakiness dashboard web client.
type BuilderTestHistory struct {
	// BuildNumbers lists the builds it knows about, in reverse chronological order.
	BuildNumbers []int64 `json:"buildNumbers"`
	// ChromeRevision lists the revision for each build.
	ChromeRevision []string `json:"chromeRevision"`
	// SecondsSinceEpoch contains some kind of timing information, which
	// isn't currently used but should be.
	SecondsSinceEpoch []int `json:"secondsSinceEpoch"`
	// Tests is a map of test name to the history of results for test runs.
	Tests map[string]*TestResultHistory `json:"tests"`
	// FailureMap is used to decode result strings in TestResultHistory.
	FailureMap map[string]string `json:"failure_map"`
}

// IndexForBuildNum returns an index for a build number, usable to find ChromeRevison and individual test run results.
func (br *BuilderTestHistory) IndexForBuildNum(buildNum int64) (int, error) {
	for i, val := range br.BuildNumbers {
		if buildNum == val {
			return i, nil
		}
	}

	return -1, fmt.Errorf("buildNumber not found: %d", buildNum)
}

// ResultsForBuildRange reutrns a continuous array of test results for a particular test
// starting at latest and going back to earliest (inclusive).
func (br *BuilderTestHistory) ResultsForBuildRange(testName string, latest, earliest int64) ([]*BuildTestResults, error) {
	startIdx, err := br.IndexForBuildNum(latest)
	if err != nil {
		return nil, err
	}
	endIdx, err := br.IndexForBuildNum(earliest)
	if err != nil {
		return nil, err
	}

	ret := []*BuildTestResults{}
	for i := startIdx; i <= endIdx; i++ {
		res, err := br.ResultsAtIndex(testName, i)
		if err != nil {
			return nil, err
		}
		ret = append(ret, &BuildTestResults{
			ChromeRevision: br.ChromeRevision[i],
			BuildNumber:    br.BuildNumbers[i],
			Results:        res,
		})
	}
	return ret, nil
}

// ResultsAtBuildNum returns an array of FailureMap'd result strings for a given test
// and build number.
func (br *BuilderTestHistory) ResultsAtBuildNum(testName string, buildNum int64) ([]string, error) {
	idx, err := br.IndexForBuildNum(buildNum)
	if err != nil {
		return nil, err
	}
	return br.ResultsAtIndex(testName, idx)
}

// ResultsAtIndex returns an array of FailureMap'd result strings for a given test
// and index.
func (br *BuilderTestHistory) ResultsAtIndex(testName string, idx int) ([]string, error) {
	test, ok := br.Tests[testName]
	if !ok {
		return nil, fmt.Errorf("test name not found: %s", testName)
	}

	resultStr, err := test.ResultAt(idx)
	if err != nil {
		return nil, err
	}

	// Decode result string into result array.
	res := []string{}
	for _, c := range resultStr {
		res = append(res, br.FailureMap[string(c)])
	}

	return res, err
}

// BuildTestResults represents the output of one test on one build.
type BuildTestResults struct {
	// ChromeRevision is the commit position the run was built at.
	ChromeRevision string
	// BuildNumber is the number of the build that ran the test.
	BuildNumber int64
	// Results is a string of characters, each of which represents a test run attempt.
	// They can be decoded, in order, using BuilderTestHistory.FailureMap.
	Results []string
}

// TestResultHistory represents the run hisotry of a given test on a given builder.
type TestResultHistory struct {
	// Results is a run-length encoded array of [count int, value string] 2-element arrays.
	Results [][]interface{}
	// Times contains timing information about the runs.
	Times [][]int
}

// ResultAt returns the test result at the given index in its history.
func (trh *TestResultHistory) ResultAt(index int) (string, error) {
	// Decode RLE of Results.
	sum := 0
	for _, res := range trh.Results {
		sum += int(res[0].(float64))
		if sum > index {
			return res[1].(string), nil
		}
	}

	return "", fmt.Errorf("Index out of range: %d", index)
}
