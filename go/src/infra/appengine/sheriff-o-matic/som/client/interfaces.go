package client

import (
	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
	"infra/monitoring/messages"
)

// CrBug returns bug information.
type CrBug interface {
	// CrBugItems returns issue matching label.
	CrbugItems(ctx context.Context, label string) ([]messages.CrbugItem, error)
}

// FindIt returns FindIt information.
type FindIt interface {
	// FinditBuildbucket returns FindIt results for a build. Both input and output are using buildbucket concepts.
	FinditBuildbucket(ctx context.Context, buildID int64, failedSteps []string) ([]*messages.FinditResultV2, error)
}

// CrRev returns redirects for commit positions.
type CrRev interface {
	// GetRedirect gets the redirect for a commit position.
	GetRedirect(c context.Context, pos string) (map[string]string, error)
}

// TestResults returns test results for give step.
type TestResults interface {
	// GetTestResults returns the currently registered test-results client, or panics.
	TestResults(ctx context.Context, master *messages.MasterLocation, builderName, stepName string, buildNumber int64) (*model.FullResult, error)

	// GetTestResultHistory returns the result history of a given test.
	GetTestResultHistory(ctx context.Context, master, builderName, stepName string) (*BuilderTestHistory, error)
}
