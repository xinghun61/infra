package monorailtest

import (
	"infra/monorail"

	"golang.org/x/net/context"
)

// ServerMock delegates method implementations to function pointers.
// If the function pointer is not initialized, the method panics.
type ServerMock struct {
	InsertIssueImpl   func(context.Context, *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error)
	InsertCommentImpl func(context.Context, *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error)
	IssuesListImpl    func(context.Context, *monorail.IssuesListRequest) (*monorail.IssuesListResponse, error)
}

// InsertIssue implements MonorailServer.
func (s *ServerMock) InsertIssue(c context.Context, in *monorail.InsertIssueRequest) (*monorail.InsertIssueResponse, error) {
	return s.InsertIssueImpl(c, in)
}

// InsertComment implements MonorailServer.
func (s *ServerMock) InsertComment(c context.Context, in *monorail.InsertCommentRequest) (*monorail.InsertCommentResponse, error) {
	return s.InsertCommentImpl(c, in)
}

// IssuesList implements MonorailServer.
func (s *ServerMock) IssuesList(c context.Context, in *monorail.IssuesListRequest) (*monorail.IssuesListResponse, error) {
	return s.IssuesListImpl(c, in)
}
