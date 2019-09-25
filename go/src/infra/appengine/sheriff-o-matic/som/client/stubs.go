package client

import (
	"infra/appengine/test-results/model"
	"infra/monitoring/messages"

	"golang.org/x/net/context"
)

// StubFindIt is a stub for testing.
type StubFindIt struct {
	Result    []*messages.FinditResult
	Responses []*messages.FinditResultV2
	Err       error
}

// Findit returns Findit results.
func (fi *StubFindIt) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	return fi.Result, fi.Err
}

// FinditBuildbucket returns FinditBuildbucket results.
func (fi *StubFindIt) FinditBuildbucket(ctx context.Context, buildID int64, failedSteps []string) ([]*messages.FinditResultV2, error) {
	return fi.Responses, fi.Err
}

// StubTestResults is a stub for testing.
type StubTestResults struct {
	FullResult         *model.FullResult
	BuilderTestHistory *BuilderTestHistory
	Err                error
}

// TestResults returns test results.
func (tr *StubTestResults) TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*model.FullResult, error) {
	return tr.FullResult, tr.Err
}

// GetTestResultHistory returns test results history.
func (tr *StubTestResults) GetTestResultHistory(ctx context.Context, master, builderName, stepName string) (*BuilderTestHistory, error) {
	return tr.BuilderTestHistory, tr.Err
}
