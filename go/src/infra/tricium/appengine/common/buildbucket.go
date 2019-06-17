// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"go.chromium.org/luci/buildbucket/proto"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	fm "google.golang.org/genproto/protobuf/field_mask"

	admin "infra/tricium/api/admin/v1"
)

const (
	buildbucketBasePath = "/_ah/api/buildbucket/v1/builds"
	bucket              = "luci.tricium.try"
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

	parametersJSON, err := swarmingParametersJSON(params.Worker, recipe)
	if err != nil {
		return nil, err
	}

	req := makeRequest(topic(c), params.PubsubUserdata, parametersJSON, params.Tags)
	logging.Fields{
		"bucket": req.Bucket,
		"tags":   req.Tags,
		"params": req.ParametersJson,
	}.Infof(c, "Making Buildbucket Trigger request.")
	res, err := buildbucketService.Put(req).Context(c).Do()
	if err != nil {
		return nil, errors.Annotate(err, "failed to trigger buildbucket build").Err()
	}
	if res == nil || res.Build == nil {
		return nil, errors.Reason("empty buildbucket response %+v", res).Err()
	}

	resJSON, err := json.MarshalIndent(res, "", "  ")
	if err != nil {
		return nil, errors.Annotate(err, "could not marshal JSON response").Err()
	}
	logging.Infof(c, "Scheduled new build: %s", resJSON)
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

	// Collect result.
	build, err := buildbucketService.GetBuild(c, &buildbucketpb.GetBuildRequest{
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

func swarmingParametersJSON(worker *admin.Worker, recipe *admin.Worker_Recipe) (string, error) {
	// Set up properties.
	properties := make(map[string]interface{})
	if recipe.Recipe.Properties != "" {
		err := json.Unmarshal([]byte(recipe.Recipe.Properties), &properties)
		if err != nil {
			return "", errors.Annotate(err, "failed to unmarshal").Err()
		}
	}

	// We don't want to include "pool" in the request to buildbucket; the pool
	// is already defined in the builder definition in cr-buildbucket.cfg.
	var dimensions []string
	for _, d := range worker.Dimensions {
		if !strings.HasPrefix(d, "pool:") {
			dimensions = append(dimensions, d)
		}
	}

	parameters := map[string]interface{}{
		"builder_name": "tricium",
		"properties":   properties,
		"swarming": map[string]interface{}{
			"override_builder_cfg": map[string]interface{}{
				"dimensions": dimensions,
				"recipe": map[string]interface{}{
					"name":         recipe.Recipe.Name,
					"cipd_package": recipe.Recipe.CipdPackage,
					"cipd_version": recipe.Recipe.CipdVersion,
				},
				"execution_timeout_secs": worker.Deadline,
			},
		},
	}
	parametersJSON, err := json.Marshal(parameters)
	if err != nil {
		return "", errors.Annotate(err, "could not marshal recipe into JSON").Err()
	}

	return string(parametersJSON), err
}

func makeRequest(pubsubTopic, pubsubUserdata, parametersJSON string, tags []string) *bbapi.LegacyApiPutRequestMessage {
	return &bbapi.LegacyApiPutRequestMessage{
		Bucket: bucket,
		PubsubCallback: &bbapi.LegacyApiPubSubCallbackMessage{
			Topic:    pubsubTopic,
			UserData: pubsubUserdata,
		},
		Tags:           tags,
		ParametersJson: parametersJSON,
	}
}
