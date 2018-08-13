// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"encoding/json"
	"fmt"

	"go.chromium.org/luci/buildbucket/proto"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"golang.org/x/net/context"
	fm "google.golang.org/genproto/protobuf/field_mask"

	admin "infra/tricium/api/admin/v1"
)

const (
	buildbucketBasePath = "/_ah/api/buildbucket/v1/builds"
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
	buildbucketService, err := bbapi.New(oauthClient)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create buildbucket client").Err()
	}

	buildbucketService.BasePath = fmt.Sprintf("https://%s%s", params.Server, buildbucketBasePath)

	// Prepare recipe details.
	recipe, ok := params.Worker.Impl.(*admin.Worker_Recipe)
	if !ok {
		return nil, errors.Annotate(err, "buildbucket client function must be a recipe").Err()
	}

	parametersJSON, err := swarmingParametersJSON(params.Server, params.Worker, recipe)
	if err != nil {
		return nil, err
	}

	req := makeRequest(topic(c), params.PubsubUserdata, parametersJSON, params.Tags)
	logging.Fields{
		"bucket": req.Bucket,
		"tags":   req.Tags,
		"params": req.ParametersJson,
	}.Infof(c, "[buildbucket] Trigger request.")
	res, err := buildbucketService.Put(req).Context(c).Do()
	if err != nil || res.Build == nil {
		return nil, errors.Annotate(err, "failed to trigger buildbucket build").Err()
	}

	resJSON, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		return nil, errors.Annotate(err, "could not marshal JSON response").Err()
	}
	logging.Infof(c, "scheduled new build: %s", resJSON)
	return &TriggerResult{BuildID: res.Build.Id}, nil
}

// Collect implements the TaskServerAPI.
func (s buildbucketServer) Collect(c context.Context, params *CollectParameters) (*CollectResult, error) {
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create oauth client").Err()
	}
	buildbucketService := buildbucketpb.NewBuildsPRPCClient(&prpc.Client{
		C:    oauthClient,
		Host: params.Server,
	})

	// Collect result
	build, err := buildbucketService.GetBuild(c, &buildbucketpb.GetBuildRequest{
		Id:     params.BuildID,
		Fields: &fm.FieldMask{Paths: []string{"output.properties.comments", "status"}},
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
	result.BuildbucketOutput = build.GetOutput().GetProperties().GetFields()["comments"].GetStringValue()
	return result, nil
}

func swarmingParametersJSON(serverURL string, worker *admin.Worker, recipe *admin.Worker_Recipe) (string, error) {
	// Prepare swarming overrides.
	parameters := map[string]interface{}{
		"builder_name": "tricium",
		"swarming": map[string]interface{}{
			"hostname": serverURL,
			"override_builder_cfg": map[string]interface{}{
				"dimensions": worker.Dimensions,
				"recipe":     recipe.Recipe.Name,
			},
		},
	}
	parametersJSON, err := json.Marshal(parameters)
	if err != nil {
		return "", errors.Annotate(err, "could not marshal recipe into JSON").Err()
	}

	return string(parametersJSON), err
}

func makeRequest(pubsubTopic, pubsubUserdata, parametersJSON string, tags []string) *bbapi.ApiPutRequestMessage {
	return &bbapi.ApiPutRequestMessage{
		Bucket: "luci.infra.tricium",
		PubsubCallback: &bbapi.ApiPubSubCallbackMessage{
			Topic:    pubsubTopic,
			UserData: pubsubUserdata,
		},
		Tags:           tags,
		ParametersJson: parametersJSON,
	}
}
