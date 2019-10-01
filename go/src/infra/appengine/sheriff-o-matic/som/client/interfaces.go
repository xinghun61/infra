package client

import (
	"golang.org/x/net/context"

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
