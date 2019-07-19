// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"

	"github.com/golang/protobuf/jsonpb"
	structpb "github.com/golang/protobuf/ptypes/struct"

	"go.chromium.org/luci/auth/client/authcli"
	buildbucket_pb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/grpc/prpc"

	"infra/cmd/skylab/internal/cmd/recipe"
	"infra/cmd/skylab/internal/site"
)

func buildbucketRun(ctx context.Context, args recipe.Args, env site.Environment, authFlags authcli.Flags) error {
	req := recipe.Request(args)

	// Do a JSON roundtrip to turn req (a proto) into a structpb.
	m := jsonpb.Marshaler{}
	json, err := m.MarshalToString(req)
	if err != nil {
		return err
	}
	reqStruct := &structpb.Struct{}
	if err := jsonpb.UnmarshalString(json, reqStruct); err != nil {
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

	hClient, err := httpClient(ctx, &authFlags)
	if err != nil {
		return err
	}

	pClient := &prpc.Client{
		C:    hClient,
		Host: env.BuildbucketHost,
	}

	bClient := buildbucket_pb.NewBuildsPRPCClient(pClient)
	build, err := bClient.ScheduleBuild(ctx, bbReq)
	if err != nil {
		return err
	}

	fmt.Printf("Created request at %s\n", bbURL(env, build.Id))

	return nil
}

func bbURL(e site.Environment, buildID int64) string {
	return fmt.Sprintf("https://ci.chromium.org/p/%s/builders/%s/%s/b%d",
		e.BuildbucketProject, e.BuildbucketBucket, e.BuildbucketBuilder, buildID)
}
