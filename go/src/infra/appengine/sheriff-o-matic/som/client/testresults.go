package client

import (
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
