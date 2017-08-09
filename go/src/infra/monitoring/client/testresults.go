package client

import (
	"fmt"
	"net/url"

	"infra/monitoring/messages"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/logging"
)

type testResults struct {
	simpleClient
}

// TestResults fetches the results of a step failure's test run.
func (trc *testResults) TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
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
	trc := &testResults{simpleClient{Host: host, Client: nil}}
	return context.WithValue(ctx, testResultsKey, trc)
}

// GetTestResults returns the currently registered test-results client, or panics.
func GetTestResults(ctx context.Context) *testResults {
	ret, ok := ctx.Value(testResultsKey).(*testResults)
	if !ok {
		panic("No test-results client set in context")
	}
	return ret
}
