// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"fmt"
	"strconv"

	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	fm "google.golang.org/genproto/protobuf/field_mask"

	admin "infra/tricium/api/admin/v1"
)

// BuildbucketServer implements the ServerAPI for the buildbucket service.
// TODO: Replace this with a more usable interface.
var BuildbucketServer buildbucketServer

type buildbucketServer struct {
}

// Trigger implements the TaskServerAPI.
func (s buildbucketServer) Trigger(c context.Context, params *TriggerParameters) (*TriggerResult, error) {
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create oauth client").Err()
	}

	client := buildbucketpb.NewBuildsPRPCClient(&prpc.Client{
		C:    oauthClient,
		Host: params.Server,
	})

	return trigger(c, params, client)
}

func trigger(c context.Context, params *TriggerParameters, client buildbucketpb.BuildsClient) (*TriggerResult, error) {
	// Prepare recipe details.
	recipe, ok := params.Worker.Impl.(*admin.Worker_Recipe)
	if !ok {
		return nil, errors.Reason("buildbucket client function must be a recipe").Err()
	}

	// Extract change and patchset.
	change, err := strconv.ParseInt(params.Patch.GerritCl, 10, 64)
	if err != nil {
		return nil, errors.Annotate(err, "unable to parse Gerrit change").Err()
	}
	patchset, err := strconv.ParseInt(params.Patch.GerritPatch, 10, 64)
	if err != nil {
		return nil, errors.Annotate(err, "unable to parse Gerrit patchset").Err()
	}

	// Trigger build.
	build, err := client.ScheduleBuild(c, &buildbucketpb.ScheduleBuildRequest{
		RequestId: fmt.Sprintf("%s~%s~%s", params.Patch.GerritProject, params.Patch.GerritCl, params.Patch.GerritPatch),
		Builder: &buildbucketpb.BuilderID{
			Project: recipe.Recipe.Project,
			Bucket:  recipe.Recipe.Bucket,
			Builder: recipe.Recipe.Builder,
		},
		GerritChanges: []*buildbucketpb.GerritChange{{
			Host:     params.Patch.GerritHost,
			Project:  params.Patch.GerritProject,
			Change:   change,
			Patchset: patchset,
		}},
		Notify: &buildbucketpb.NotificationConfig{
			PubsubTopic: topic(c),
			UserData:    []byte(params.PubsubUserdata),
		},
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to trigger for buildbucket task").Err()
	}

	logging.Infof(c, "Scheduled new build: %s", build.String())
	return &TriggerResult{BuildID: build.Id}, nil
}

// Collect implements the TaskServerAPI.
func (s buildbucketServer) Collect(c context.Context, params *CollectParameters) (*CollectResult, error) {
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create oauth client").Err()
	}
	client := buildbucketpb.NewBuildsPRPCClient(&prpc.Client{
		C:    oauthClient,
		Host: params.Server,
	})

	return collect(c, params, client)
}

func collect(c context.Context, params *CollectParameters, client buildbucketpb.BuildsClient) (*CollectResult, error) {
	// Collect result.
	build, err := client.GetBuild(c, &buildbucketpb.GetBuildRequest{
		Id:     params.BuildID,
		Fields: &fm.FieldMask{Paths: []string{"output.properties.fields.tricium", "status"}},
	})
	if err != nil {
		return nil, errors.Annotate(err, "failed to collect results for buildbucket task").Err()
	}

	result := &CollectResult{}
	switch build.Status {
	case buildbucketpb.Status_SCHEDULED, buildbucketpb.Status_STARTED:
		result.State = Pending
	case buildbucketpb.Status_SUCCESS:
		result.State = Success
	default:
		result.State = Failure
	}

	logging.Fields{
		"output_properties": build.GetOutput().GetProperties(),
	}.Debugf(c, "Getting output properties")
	result.BuildbucketOutput = build.GetOutput().GetProperties().GetFields()["tricium"].GetStringValue()
	if result.BuildbucketOutput == "" {
		logging.Fields{
			"buildID":    params.BuildID,
			"buildState": result.State,
		}.Infof(c, "Result had no output.")
	}
	return result, nil
}
