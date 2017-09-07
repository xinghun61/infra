package test

import (
	"fmt"
	"time"

	"golang.org/x/net/context"

	"infra/monitoring/messages"
)

func fakeNow(t time.Time) func() time.Time {
	return func() time.Time {
		return t
	}
}

// MockReader is a mock reader used for testing.
type MockReader struct {
	BCache            map[string]*messages.Build
	BuildValue        *messages.Build
	Builds            map[string]*messages.Build
	LatestBuildsValue map[messages.MasterLocation]map[string][]*messages.Build
	TestResultsValue  *messages.TestResults
	StdioForStepValue []string
	FinditResults     []*messages.FinditResult
	BuildFetchError,
	StepFetchError,
	StdioForStepError error
	BuildFetchErrs map[string]error
	BuildExtracts  map[string]*messages.BuildExtract
}

// Build implements the Reader interface.
func (m MockReader) Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	if m.BuildValue != nil || m.BuildFetchError != nil {
		return m.BuildValue, m.BuildFetchError
	}

	key := fmt.Sprintf("%s/%s/%d", master.Name(), builder, buildNum)
	if b, ok := m.BCache[key]; ok {
		return b, nil
	}
	return m.Builds[key], m.BuildFetchErrs[key]
}

// LatestBuilds implements the Reader interface.
func (m MockReader) LatestBuilds(ctx context.Context, master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	return m.LatestBuildsValue[*master][builder], nil
}

// TestResults implements the Reader interface.
func (m MockReader) TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	return m.TestResultsValue, m.StepFetchError
}

// BuildExtract implements the Reader interface.
func (m MockReader) BuildExtract(ctx context.Context, url *messages.MasterLocation) (*messages.BuildExtract, error) {
	if be, ok := m.BuildExtracts[url.Name()]; ok {
		return be, nil
	}
	return nil, fmt.Errorf("master not found: %s", url.Name())
}

// StdioForStep implements the Reader interface.
func (m MockReader) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	return m.StdioForStepValue, m.StdioForStepError
}

// JSON implements the Reader interface.
func (m MockReader) JSON(ctx context.Context, url string, v interface{}) (int, error) {
	return 0, nil // Not actually used.
}

// PostAlerts implements the Reader interface.
func (m MockReader) PostAlerts(ctx context.Context, alerts *messages.Alerts) error {
	return nil
}

// CrbugItems implements the Reader interface.
func (m MockReader) CrbugItems(ctx context.Context, tree string) ([]messages.CrbugItem, error) {
	return nil, nil
}

// Findit implements the Reader interface.
func (m MockReader) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	return m.FinditResults, nil
}
