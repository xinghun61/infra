// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package bb provides a buildbucket Client with helper methods for interacting
// with builds.
package bb

import (
	"context"
	"fmt"
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

	recipeStruct := &structpb.Struct{}
	recipeStruct.Fields = map[string]*structpb.Value{
		"request": {Kind: &structpb.Value_StructValue{StructValue: reqStruct}},
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
		return nil, err
	}
	return extractResponse(build)
}

// BuildURL constructs the URL to a build with the given ID.
func (c *Client) BuildURL(buildID int64) string {
	return fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s/b%d",
		c.env.BuildbucketProject, c.env.BuildbucketBucket, c.env.BuildbucketBuilder, buildID)
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

func (c *Client) waitForBuild(ctx context.Context, buildID int64) (*buildbucket_pb.Build, error) {
	throttledLogger := logutils.NewThrottledInfoLogger(logging.Get(ctx), 5*time.Minute)
	progressMessage := fmt.Sprintf("Still waiting for result from testplatform build ID %d", buildID)

	fields := &field_mask.FieldMask{Paths: getBuildFields}
	req := &buildbucket_pb.GetBuildRequest{
		Id:     buildID,
		Fields: fields,
	}

	for {
		build, err := c.client.GetBuild(ctx, req)
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

func extractResponse(build *buildbucket_pb.Build) (*steps.ExecuteResponse, error) {
	properties := build.GetOutput().GetProperties()
	responseStruct, ok := properties.GetFields()["response"]
	if !ok {
		return nil, errors.Reason("build properties contained no `response` field").Err()
	}

	// Do a JSON roundtrip to turn response (a structpb) into response proto.
	m := jsonpb.Marshaler{}
	json, err := m.MarshalToString(responseStruct)
	if err != nil {
		return nil, err
	}
	response := &steps.ExecuteResponse{}
	if err := jsonpb.UnmarshalString(json, response); err != nil {
		return nil, err
	}

	return response, nil
}

func isFinal(status buildbucket_pb.Status) bool {
	return (status & buildbucket_pb.Status_ENDED_MASK) == buildbucket_pb.Status_ENDED_MASK
}
