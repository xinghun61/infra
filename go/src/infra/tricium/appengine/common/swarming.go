// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"fmt"
	"strings"
	"time"

	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolatedclient"
	"go.chromium.org/luci/common/logging"
)

const (
	swarmingBasePath      = "/_ah/api/swarming/v1/"
	swarmingDevServerURL  = "https://chromium-swarm-dev.appspot.com"
	swarmingProdServerURL = "https://chromium-swarm.appspot.com"
)

// SwarmingServer implements the TaskServerAPI for the swarming service.
var SwarmingServer swarmingServer

type swarmingServer struct {
}

// Trigger implements the TaskServerAPI.
func (s swarmingServer) Trigger(c context.Context, params *TriggerParameters) (*TriggerResult, error) {
	pubsubTopic := topic(c)
	// Prepare task dimensions.
	dims := []*swarming.SwarmingRpcsStringPair{}
	for _, d := range params.Worker.Dimensions {
		// Extracting dimension key and value.
		// Note that ':' may appear in the value but not the key.
		dim := strings.SplitN(d, ":", 2)
		if len(dim) != 2 {
			return nil, errors.Reason("failed to split dimension: %q", d).Err()
		}
		dims = append(dims, &swarming.SwarmingRpcsStringPair{Key: dim[0], Value: dim[1]})
	}
	// Prepare CIPD input packages.
	cipd := &swarming.SwarmingRpcsCipdInput{}
	for _, p := range params.Worker.CipdPackages {
		cipd.Packages = append(cipd.Packages, &swarming.SwarmingRpcsCipdPackage{
			PackageName: p.PackageName,
			Path:        p.Path,
			Version:     p.Version,
		})
	}
	// Need to increase the timeout to get a response from the Swarming service.
	c, cancel := context.WithTimeout(c, 60*time.Second)
	defer cancel()
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create oauth client").Err()
	}
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create swarming client").Err()
	}
	// TODO(qyearsley): Read timeouts from the analyzer config.
	// Prepare properties.
	props := &swarming.SwarmingRpcsTaskProperties{
		Dimensions:           dims,
		ExecutionTimeoutSecs: 600,
		IoTimeoutSecs:        600,
		InputsRef: &swarming.SwarmingRpcsFilesRef{
			Isolated:       params.WorkerIsolate,
			Isolatedserver: params.IsolateServerURL,
			Namespace:      isolatedclient.DefaultNamespace,
		},
	}
	// Only include CIPD input if there are packages.
	if len(cipd.Packages) > 0 {
		props.CipdInput = cipd
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", params.Server, swarmingBasePath)
	res, err := swarmingService.Tasks.New(&swarming.SwarmingRpcsNewTaskRequest{
		Name:     "tricium:" + params.Worker.Name,
		Priority: 100,
		TaskSlices: []*swarming.SwarmingRpcsTaskSlice{
			{
				Properties:     props,
				ExpirationSecs: 21600,
			},
		},
		PubsubTopic:    pubsubTopic,
		PubsubUserdata: params.PubsubUserdata,
		Tags:           params.Tags,
	}).Do()
	if err != nil {
		return nil, errors.Annotate(err, "failed to trigger swarming task").Err()
	}
	logging.Fields{
		"taskID":       res.TaskId,
		"worker":       params.Worker.Name,
		"dimensions":   dims,
		"pubsubTopic":  pubsubTopic,
		"inputIsolate": params.WorkerIsolate,
	}.Infof(c, "Worker triggered")
	return &TriggerResult{TaskID: res.TaskId}, nil
}

// Collect implements the TaskServerAPI.
func (s swarmingServer) Collect(c context.Context, params *CollectParameters) (*CollectResult, error) {
	// Need to increase the timeout to get a response from the Swarming service.
	c, cancel := context.WithTimeout(c, 60*time.Second)
	defer cancel()
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create oauth client").Err()
	}
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create swarming client").Err()
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", params.Server, swarmingBasePath)
	taskResult, err := swarmingService.Task.Result(params.TaskID).Do()
	if err != nil {
		return nil, errors.Annotate(err, "failed to retrieve task result from swarming").Err()
	}

	result := &CollectResult{}
	if taskResult.OutputsRef == nil || taskResult.OutputsRef.Isolated == "" {
		logging.Fields{
			"taskID":    params.TaskID,
			"taskState": result.State,
		}.Infof(c, "Task had no output.")
	} else {
		result.IsolatedNamespace = taskResult.OutputsRef.Namespace
		result.IsolatedOutputHash = taskResult.OutputsRef.Isolated
	}

	if taskResult.State == "COMPLETED" {
		if taskResult.ExitCode != 0 {
			result.State = Failure
		} else {
			result.State = Success
		}
	} else if taskResult.State == "PENDING" || taskResult.State == "RUNNING" {
		result.State = Pending
	} else {
		result.State = Failure
	}

	return result, nil
}
