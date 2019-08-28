// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package bb provides a buildbucket Client with helper methods for interacting
// with builds.
package bb

import (
	"context"
	"fmt"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/golang/protobuf/jsonpb"
	structpb "github.com/golang/protobuf/ptypes/struct"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	buildbucket_pb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"google.golang.org/genproto/protobuf/field_mask"

	"infra/cmd/skylab/internal/logutils"
	"infra/cmd/skylab/internal/site"
)

// NewClient returns a new client to interact with buildbucket builds.
func NewClient(ctx context.Context, env site.Environment, authFlags authcli.Flags) (*Client, error) {
	hClient, err := newHTTPClient(ctx, &authFlags)
	if err != nil {
		return nil, err
	}

	pClient := &prpc.Client{
		C:    hClient,
		Host: env.BuildbucketHost,
	}

	return &Client{
		client: buildbucket_pb.NewBuildsPRPCClient(pClient),
		env:    env,
	}, nil
}

// Client provides helper methods to interact with buildbucket builds.
type Client struct {
	client buildbucket_pb.BuildsClient
	env    site.Environment
}

// newHTTPClient returns an HTTP client with authentication set up.
//
// TODO(pprabhu) dedup with internal/cmd/common.go:newHTTPClient
func newHTTPClient(ctx context.Context, f *authcli.Flags) (*http.Client, error) {
	o, err := f.Options()
	if err != nil {
		return nil, errors.Annotate(err, "failed to get auth options").Err()
	}
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, o)
	c, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	return c, nil
}

// ScheduleBuild schedules a new cros_test_platform build.
//
// ScheduleBuild returns the buildbucket build ID for the scheduled build on
// success.
// ScheduleBuild does not wait for the scheduled build to start.
func (c *Client) ScheduleBuild(ctx context.Context, request *test_platform.Request, tags []string) (int64, error) {
	// Do a JSON roundtrip to turn req (a proto) into a structpb.
	m := jsonpb.Marshaler{}
	jsonStr, err := m.MarshalToString(request)
	if err != nil {
		return -1, err
	}
	reqStruct := &structpb.Struct{}
	if err := jsonpb.UnmarshalString(jsonStr, reqStruct); err != nil {
		return -1, err
	}

	return c.ScheduleBuildRaw(ctx, reqStruct, tags)
}

// ScheduleBuildRaw schedules a new cros_test_platform build.
//
// The request argument is a structpb Struct for a cros_test_platform.Request as
// expected by the buildbucket API. ScheduledBuildRaw is useful in cases where
// there is a need to avoid parsing a request Struct obtained from another
// buildbucket build.
func (c *Client) ScheduleBuildRaw(ctx context.Context, request *structpb.Struct, tags []string) (int64, error) {
	recipeStruct := &structpb.Struct{}
	recipeStruct.Fields = map[string]*structpb.Value{
		"request": {Kind: &structpb.Value_StructValue{StructValue: request}},
	}
	tagPairs, err := splitTagPairs(tags)
	if err != nil {
		return -1, err
	}

	bbReq := &buildbucket_pb.ScheduleBuildRequest{
		Builder: &buildbucket_pb.BuilderID{
			Project: c.env.BuildbucketProject,
			Bucket:  c.env.BuildbucketBucket,
			Builder: c.env.BuildbucketBuilder,
		},
		Properties: recipeStruct,
		Tags:       tagPairs,
	}

	build, err := c.client.ScheduleBuild(ctx, bbReq)
	if err != nil {
		return -1, err
	}
	return build.Id, nil
}

// WaitForBuild waits for a buildbucket build and returns the response on build
// completion.
//
// WaitForBuild regularly logs output to stdout to pacify the logdog silence
// checker.
func (c *Client) WaitForBuild(ctx context.Context, ID int64) (*steps.ExecuteResponse, error) {
	build, err := c.waitForBuild(ctx, ID)
	if err != nil {
		return nil, errors.Annotate(err, "wait for build %d", ID).Err()
	}
	return build.Response, nil
}

// Build contains selected state information from a fetched buildbucket Build.
type Build struct {
	Status   buildbucket_pb.Status
	Response *steps.ExecuteResponse
	// RawRequest is the unmarshalled Request from the build.
	// RawRequest is not interpreted as a test_platform.Request to avoid
	// compatibility issues arising from skylab tool's test_platform API
	// version.
	RawRequest *structpb.Struct
}

// GetBuild gets a buildbucket build by ID.
func (c *Client) GetBuild(ctx context.Context, ID int64) (*Build, error) {
	req := &buildbucket_pb.GetBuildRequest{
		Id:     ID,
		Fields: &field_mask.FieldMask{Paths: getBuildFields},
	}
	build, err := c.client.GetBuild(ctx, req)
	if err != nil {
		return nil, errors.Annotate(err, "get build").Err()
	}
	return extractBuildData(build)
}

// SearchBuildsByTags searches for all buildbucket builds with the given tags.
//
// SearchBuildsByTags returns at most limit results.
func (c *Client) SearchBuildsByTags(ctx context.Context, limit int, tags ...string) ([]*Build, error) {
	if len(tags) == 0 {
		return nil, errors.Reason("must provide at least one tag").Err()
	}
	tps, err := splitTagPairs(tags)
	if err != nil {
		return nil, errors.Annotate(err, "search builds by tags").Err()
	}
	rawBuilds, err := c.searchRawBuilds(ctx, limit, &buildbucket_pb.BuildPredicate{Tags: tps})
	if err != nil {
		return nil, errors.Annotate(err, "search builds by tags").Err()
	}
	return extractBuildDataAll(rawBuilds)
}

// BuildURL constructs the URL to a build with the given ID.
func (c *Client) BuildURL(buildID int64) string {
	return fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s/b%d",
		c.env.BuildbucketProject, c.env.BuildbucketBucket, c.env.BuildbucketBuilder, buildID)
}

func (c *Client) searchRawBuilds(ctx context.Context, limit int, predicate *buildbucket_pb.BuildPredicate) ([]*buildbucket_pb.Build, error) {
	rawBuilds := make([]*buildbucket_pb.Build, 0, limit)
	pageToken := ""
	// Each page request sets the same PageSize (limit) the SearchBuilds() rpc
	// requires the PageSize to be unchanged across page requests.
	// We could obtain more than limit results in this process, so only the
	// first limit results are returned at the end of this function.
	for {
		req := buildbucket_pb.SearchBuildsRequest{
			Predicate: predicate,
			Fields:    &field_mask.FieldMask{Paths: getSearchBuildsFields()},
			PageToken: pageToken,
			PageSize:  clipToInt32(limit),
		}
		resp, err := c.client.SearchBuilds(ctx, &req)
		if err != nil {
			return nil, errors.Annotate(err, "search raw builds").Err()
		}
		rawBuilds = append(rawBuilds, resp.GetBuilds()...)
		pageToken := resp.GetNextPageToken()
		if pageToken == "" || len(rawBuilds) >= limit {
			break
		}
	}
	return rawBuilds[:limit], nil
}

func clipToInt32(n int) int32 {
	if n <= math.MaxInt32 {
		return int32(n)
	}
	return math.MaxInt32
}

func (c *Client) waitForBuild(ctx context.Context, buildID int64) (*Build, error) {
	throttledLogger := logutils.NewThrottledInfoLogger(logging.Get(ctx), 10*time.Minute)
	progressMessage := fmt.Sprintf("Still waiting for result from %s", c.BuildURL(buildID))
	for {
		build, err := c.GetBuild(ctx, buildID)
		if err != nil {
			return nil, err
		}
		if isFinal(build.Status) {
			return build, nil
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(15 * time.Second):
		}
		throttledLogger.MaybeLog(progressMessage)
	}
}

func splitTagPairs(tags []string) ([]*buildbucket_pb.StringPair, error) {
	ret := make([]*buildbucket_pb.StringPair, 0, len(tags))
	for _, t := range tags {
		p := strings.Split(t, ":")
		if len(p) != 2 {
			return nil, errors.Reason("malformed tag %s", t).Err()
		}
		ret = append(ret, &buildbucket_pb.StringPair{
			Key:   strings.Trim(p[0], " "),
			Value: strings.Trim(p[1], " "),
		})
	}
	return ret, nil
}

// getBuildFields is the list of buildbucket fields that are needed.
var getBuildFields = []string{
	// Build details are parsed from the build's output properties.
	"output.properties",
	// Build status is used to determine whether the build is complete.
	"status",
}

func getSearchBuildsFields() []string {
	fs := make([]string, 0, len(getBuildFields))
	for _, f := range getBuildFields {
		fs = append(fs, fmt.Sprintf("builds.*.%s", f))
	}
	return fs
}

func extractBuildData(from *buildbucket_pb.Build) (*Build, error) {
	op := from.GetOutput().GetProperties().GetFields()
	if op == nil {
		return nil, errors.Reason("build %s has no output properties", from).Err()
	}
	rawResponse, ok := op["response"]
	if !ok {
		return nil, errors.Reason("output properties for build %s has no response", from).Err()
	}

	reqValue, ok := op["request"]
	if !ok {
		return nil, errors.Reason("output properties for build %s has no request", from).Err()
	}
	var rawRequest *structpb.Struct
	switch r := reqValue.Kind.(type) {
	case *structpb.Value_StructValue:
		rawRequest = r.StructValue
	default:
		return nil, errors.Reason("output properties have malformed request %#v", reqValue).Err()
	}

	response, err := structPBToExecuteResponse(rawResponse)
	if err != nil {
		return nil, errors.Annotate(err, "extractBuildData").Err()
	}
	return &Build{
		Status:     from.GetStatus(),
		Response:   response,
		RawRequest: rawRequest,
	}, nil
}

func extractBuildDataAll(from []*buildbucket_pb.Build) ([]*Build, error) {
	builds := make([]*Build, len(from))
	for i, rb := range from {
		b, err := extractBuildData(rb)
		if err != nil {
			return nil, errors.Annotate(err, "search builds by tags").Err()
		}
		builds[i] = b
	}
	return builds, nil
}

func structPBToExecuteResponse(from *structpb.Value) (*steps.ExecuteResponse, error) {
	m := jsonpb.Marshaler{}
	json, err := m.MarshalToString(from)
	if err != nil {
		return nil, errors.Annotate(err, "structPBToExecuteResponse").Err()
	}
	response := &steps.ExecuteResponse{}
	if err := jsonpb.UnmarshalString(json, response); err != nil {
		return nil, errors.Annotate(err, "structPBToExecuteResponse").Err()
	}
	return response, nil
}

func isFinal(status buildbucket_pb.Status) bool {
	return (status & buildbucket_pb.Status_ENDED_MASK) == buildbucket_pb.Status_ENDED_MASK
}
