package monorailtest

import (
	"golang.org/x/net/context"
	"google.golang.org/grpc"

	"infra/monorail"
)

// NewTestClient creates as client based on a server implementation.
func NewTestClient(serverImpl monorail.MonorailServer) monorail.MonorailClient {
	return &testClient{serverImpl}
}

type testClient struct {
	impl monorail.MonorailServer
}

func (c *testClient) InsertIssue(ctx context.Context, in *monorail.InsertIssueRequest, opts ...grpc.CallOption) (*monorail.InsertIssueResponse, error) {
	return c.impl.InsertIssue(ctx, in)
}
func (c *testClient) InsertComment(ctx context.Context, in *monorail.InsertCommentRequest, opts ...grpc.CallOption) (*monorail.InsertCommentResponse, error) {
	return c.impl.InsertComment(ctx, in)
}
func (c *testClient) IssuesList(ctx context.Context, in *monorail.IssuesListRequest, opts ...grpc.CallOption) (*monorail.IssuesListResponse, error) {
	return c.impl.IssuesList(ctx, in)
}
