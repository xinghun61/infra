// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"time"

	"github.com/golang/protobuf/jsonpb"
	structpb "github.com/golang/protobuf/ptypes/struct"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_tool"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth/client/authcli"
	buildbucket_pb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"google.golang.org/genproto/protobuf/field_mask"

	"infra/cmd/skylab/internal/cmd/recipe"
	"infra/cmd/skylab/internal/site"
)

func buildbucketRun(ctx context.Context, args recipe.Args, env site.Environment, authFlags authcli.Flags, jsonOut bool, w io.Writer) error {
	req, err := recipe.Request(args)
	if err != nil {
		return err
	}

	// Do a JSON roundtrip to turn req (a proto) into a structpb.
	m := jsonpb.Marshaler{}
	jsonStr, err := m.MarshalToString(req)
	if err != nil {
		return err
	}
	reqStruct := &structpb.Struct{}
	if err := jsonpb.UnmarshalString(jsonStr, reqStruct); err != nil {
		return err
	}

	recipeStruct := &structpb.Struct{}
	recipeStruct.Fields = map[string]*structpb.Value{
		"request": {Kind: &structpb.Value_StructValue{StructValue: reqStruct}},
	}

	bbReq := &buildbucket_pb.ScheduleBuildRequest{
		Builder: &buildbucket_pb.BuilderID{
			Project: env.BuildbucketProject,
			Bucket:  env.BuildbucketBucket,
			Builder: env.BuildbucketBuilder,
		},
		Properties: recipeStruct,
	}

	bClient, err := bbClient(ctx, env, authFlags)
	if err != nil {
		return err
	}

	build, err := bClient.ScheduleBuild(ctx, bbReq)
	if err != nil {
		return err
	}

	if jsonOut {
		ti := &taskInfo{
			Name: "cros_test_platform",
			ID:   fmt.Sprintf("%d", build.Id),
			URL:  fmt.Sprintf(bbURL(env, build.Id)),
		}
		return json.NewEncoder(w).Encode(ti)
	}

	fmt.Fprintf(w, "Created request at %s\n", bbURL(env, build.Id))

	return nil
}

func bbClient(ctx context.Context, env site.Environment, authFlags authcli.Flags) (buildbucket_pb.BuildsClient, error) {
	hClient, err := newHTTPClient(ctx, &authFlags)
	if err != nil {
		return nil, err
	}

	pClient := &prpc.Client{
		C:    hClient,
		Host: env.BuildbucketHost,
	}

	return buildbucket_pb.NewBuildsPRPCClient(pClient), nil
}

// getBuildFields is the list of buildbucket fields that are needed.
var getBuildFields = []string{
	// Build details are parsed from the build's output properties.
	"output.properties",
	// Build status is used to determine whether the build is complete.
	"status",
}

func waitBuildbucketTask(ctx context.Context, ID int64, client buildbucket_pb.BuildsClient, env site.Environment) (*skylab_tool.WaitTaskResult, error) {
	build, err := bbWaitBuild(ctx, client, ID)
	if err != nil {
		return nil, err
	}

	response, err := bbExtractResponse(build)
	if err != nil {
		return nil, err
	}

	return responseToTaskResult(env, ID, response), nil
}

func bbWaitBuild(ctx context.Context, client buildbucket_pb.BuildsClient, buildID int64) (*buildbucket_pb.Build, error) {
	throttledLogger := newThrottledInfoLogger(logging.Get(ctx), 5*time.Minute)
	progressMessage := fmt.Sprintf("Still waiting for result from testplatform build ID %d", buildID)

	fields := &field_mask.FieldMask{Paths: getBuildFields}
	req := &buildbucket_pb.GetBuildRequest{
		Id:     buildID,
		Fields: fields,
	}

	for {
		build, err := client.GetBuild(ctx, req)
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

func bbExtractResponse(build *buildbucket_pb.Build) (*steps.ExecuteResponse, error) {
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

func bbURL(e site.Environment, buildID int64) string {
	return fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s/b%d",
		e.BuildbucketProject, e.BuildbucketBucket, e.BuildbucketBuilder, buildID)
}
