package test

import (
	"fmt"
	"time"

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
}

// Build implements the Reader interface.
func (m MockReader) Build(master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error) {
	if m.BuildValue != nil {
		return m.BuildValue, m.BuildFetchError
	}

	key := fmt.Sprintf("%s/%s/%d", master.Name(), builder, buildNum)
	if b, ok := m.BCache[key]; ok {
		return b, nil
	}
	return m.Builds[key], m.BuildFetchErrs[key]
}

// LatestBuilds implements the Reader interface.
func (m MockReader) LatestBuilds(master *messages.MasterLocation, builder string) ([]*messages.Build, error) {
	return m.LatestBuildsValue[*master][builder], nil
}

// TestResults implements the Reader interface.
func (m MockReader) TestResults(master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*messages.TestResults, error) {
	return m.TestResultsValue, m.StepFetchError
}

// BuildExtract implements the Reader interface.
func (m MockReader) BuildExtract(url *messages.MasterLocation) (*messages.BuildExtract, error) {
	return nil, nil
}

// StdioForStep implements the Reader interface.
func (m MockReader) StdioForStep(master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	return m.StdioForStepValue, m.StdioForStepError
}

// JSON implements the Reader interface.
func (m MockReader) JSON(url string, v interface{}) (int, error) {
	return 0, nil // Not actually used.
}

// PostAlerts implements the Reader interface.
func (m MockReader) PostAlerts(alerts *messages.Alerts) error {
	return nil
}

// CrbugItems implements the Reader interface.
func (m MockReader) CrbugItems(tree string) ([]messages.CrbugItem, error) {
	return nil, nil
}

// Findit implements the Reader interface.
func (m MockReader) Findit(master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	return m.FinditResults, nil
}
