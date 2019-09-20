package client

import (
	"golang.org/x/net/context"

	"infra/appengine/test-results/model"
	"infra/monitoring/messages"

	bbpb "go.chromium.org/luci/buildbucket/proto"
)

// BuildBucket returns information about builds that run on buildbucket.
type BuildBucket interface {
	// LatestBuilds returns recent builds.
	LatestBuilds(ctx context.Context, builderIDs []*bbpb.BuilderID) ([]*bbpb.Build, error)
}

// Milo returns build information.
type Milo interface {
	// Build returns a build record.
	Build(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64) (*messages.Build, error)
	// BuildExtract returns a build extract for a master.
	BuildExtract(ctx context.Context, master *messages.MasterLocation) (*messages.BuildExtract, error)
}

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

// LogReader returns logs from build steps.
type LogReader interface {
	// StdioForStep returns stdio logs for a build step.
	StdioForStep(ctx context.Context, master *messages.MasterLocation, builder, step string, buildNum int64) ([]string, error)
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
