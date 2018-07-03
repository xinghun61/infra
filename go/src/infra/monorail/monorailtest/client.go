package monorailtest

import (
	"golang.org/x/net/context"
	"google.golang.org/grpc"

	"infra/monorail"
)

// NewClient creates as client based on a server implementation.
func NewClient(serverImpl monorail.MonorailServer) monorail.MonorailClient {
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
func (c *testClient) GetIssue(ctx context.Context, in *monorail.GetIssueRequest, opts ...grpc.CallOption) (*monorail.Issue, error) {
	return c.impl.GetIssue(ctx, in)
}
func (c *testClient) ListComments(ctx context.Context, in *monorail.ListCommentsRequest, opts ...grpc.CallOption) (*monorail.ListCommentsResponse, error) {
	return c.impl.ListComments(ctx, in)
}
