// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/isolatedclient"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"

	"golang.org/x/net/context"

	admin "infra/tricium/api/admin/v1"
)

const (
	swarmingBasePath      = "/_ah/api/swarming/v1/"
	swarmingDevServerURL  = "https://chromium-swarm-dev.appspot.com"
	swarmingProdServerURL = "https://chromium-swarm.appspot.com"
)

// SwarmingAPI specifies the Swarming service API.
type SwarmingAPI interface {
	// Trigger triggers a swarming task.
	//
	// The provided worker isolate is used for the task.
	// At completion, the swarming service will publish a message, including the provided user data, to the worker completion pubsub topic.
	Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string) (string, error)

	// Collect collects results for a swarming task with the provided ID.
	//
	// The task in question should be completed before this function is called and the
	// task should have isolated output.
	// The isolated output and exit code of the task are returned.
	Collect(c context.Context, serverURL, taskID string) (string, int64, error)
}

// SwarmingServer implements the SwarmingAPI for the swarming service.
var SwarmingServer swarmingServer

type swarmingServer struct {
}

// Trigger implements the SwarmingAPI.
func (s swarmingServer) Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string) (string, error) {
	pubsubTopic := topic(c)
	// Prepare task dimentions.
	dims := []*swarming.SwarmingRpcsStringPair{}
	for _, d := range worker.Dimensions {
		// Extracting dimension key and value. Note that ':' may appear in the value but not the key.
		dim := strings.SplitN(d, ":", 2)
		if len(dim) != 2 {
			return "", fmt.Errorf("failed to split dimension: %q", d)
		}
		dims = append(dims, &swarming.SwarmingRpcsStringPair{Key: dim[0], Value: dim[1]})
	}
	// Prepare CIPD input packages.
	cipd := &swarming.SwarmingRpcsCipdInput{}
	for _, p := range worker.CipdPackages {
		cipd.Packages = append(cipd.Packages, &swarming.SwarmingRpcsCipdPackage{
			PackageName: p.PackageName,
			Path:        p.Path,
			Version:     p.Version,
		})
	}
	// Need to increase the timeout to get a response from the Swarming service.
	c, _ = context.WithTimeout(c, 60*time.Second)
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create oauth client: %v", err)
		return "", fmt.Errorf("failed to create oauth client: %v", err)
	}
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create swarming client: %v", err)
		return "", fmt.Errorf("failed to create swarming client: %v", err)
	}
	// TODO(emso): Read timeouts from the analyzer config.
	// Prepare properties.
	props := &swarming.SwarmingRpcsTaskProperties{
		Dimensions:           dims,
		ExecutionTimeoutSecs: 600,
		IoTimeoutSecs:        600,
		InputsRef: &swarming.SwarmingRpcsFilesRef{
			Isolated:       workerIsolate,
			Isolatedserver: isolateServerURL,
			Namespace:      isolatedclient.DefaultNamespace,
		},
	}
	// Only include CIPD input if there are packages.
	if len(cipd.Packages) > 0 {
		props.CipdInput = cipd
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", serverURL, swarmingBasePath)
	res, err := swarmingService.Tasks.New(&swarming.SwarmingRpcsNewTaskRequest{
		Name:           "tricium:" + worker.Name,
		Priority:       100,
		ExpirationSecs: 21600,
		Properties:     props,
		PubsubTopic:    pubsubTopic,
		PubsubUserdata: pubsubUserdata,
	}).Do()
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to trigger swarming task: %v", err)
		return "", fmt.Errorf("failed to trigger swarming task: %v", err)
	}
	logging.Infof(c, "Worker triggered, ID: %q, name: %q, dimensions: %v, pubsub topic: %q, input isolate: %q",
		res.TaskId, worker.Name, dims, pubsubTopic, workerIsolate)
	return res.TaskId, nil
}

// Collect implements the SwarmingAPI.
func (s swarmingServer) Collect(c context.Context, serverURL, taskID string) (string, int64, error) {
	// Need to increase the timeout to get a response from the Swarming service.
	c, _ = context.WithTimeout(c, 60*time.Second)
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return "", 0, fmt.Errorf("failed to create oauth client: %v", err)
	}
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		return "", 0, fmt.Errorf("failed to create swarming client: %v", err)
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", serverURL, swarmingBasePath)
	res, err := swarmingService.Task.Result(taskID).Do()
	if err != nil {
		return "", 0, fmt.Errorf("failed to collect results for swarming task (id: %s): %v", taskID, err)
	}
	if res.OutputsRef == nil {
		return "", 0, fmt.Errorf("missing isolated output, task id: %s", taskID)
	}
	return res.OutputsRef.Isolated, res.ExitCode, nil
}

func getOAuthClient(c context.Context) (*http.Client, error) {
	// Note: "https://www.googleapis.com/auth/userinfo.email" is the default
	// scope used by GetRPCTransport(AsSelf). Use auth.WithScopes(...) option to
	// override.
	t, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return &http.Client{Transport: t}, nil
}

// MockSwarmingAPI mocks the SwarmingAPI interface for testing.
var MockSwarmingAPI mockSwarmingAPI

type mockSwarmingAPI struct {
}

// Trigger is a mock function for the MockSwarmingAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockSwarmingAPI) Trigger(c context.Context, serverURL, isolateServerURL string, worker *admin.Worker, workerIsolate, pubsubUserdata string) (string, error) {
	return "mockmockmock", nil
}

// Collect is a mock function for the MockSwarmingAPI.
//
// For any testing actually using the return value, create a new mock.
func (mockSwarmingAPI) Collect(c context.Context, serverURL string, taskID string) (string, int64, error) {
	return "mockmockmock", 0, nil
}
