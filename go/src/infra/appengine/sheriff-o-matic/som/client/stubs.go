package client

import (
	bbpb "go.chromium.org/luci/buildbucket/proto"

	"infra/appengine/test-results/model"
	"infra/monitoring/messages"

	"golang.org/x/net/context"
)

// StubBuildBucket is a stub for testing.
type StubBuildBucket struct {
	Latest []*bbpb.Build
	Err    error
}

// LatestBuilds returns latest builds.
func (bb *StubBuildBucket) LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error) {
	return bb.Latest, bb.Err
}

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

// StubLogReader is a stub for testing.
type StubLogReader struct {
	Logs []string
	Err  error
}

// StdioForStep returns stdio for the step.
func (lr *StubLogReader) StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error) {
	return lr.Logs, lr.Err
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
