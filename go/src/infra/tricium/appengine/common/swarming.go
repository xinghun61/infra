// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/isolatedclient"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/auth"

	"golang.org/x/net/context"

	admin "infra/tricium/api/admin/v1"
)

const (
	swarmingBasePath = "/_ah/api/swarming/v1/"
	// SwarmingDevServerURL specifies the URL to the swarming dev server.
	SwarmingDevServerURL = "https://chromium-swarm-dev.appspot.com"
	// SwarmingProdServerURL specifies the URL to the swarming prod server.
	SwarmingProdServerURL = "https://chromium-swarm.appspot.com"
)

// SwarmingAPI specifies the Swarming servic API.
type SwarmingAPI interface {
	Trigger(c context.Context, worker *admin.Worker, workerIsolate, pubsubUserdata, pubsubTopic string) (string, error)
	Collect(c context.Context, taskID string) (string, int64, error)
}

// SwarmingServer implements the SwarmingAPI for the swarming service.
type SwarmingServer struct {
	SwarmingServerURL string
	IsolateServerURL  string
}

// Trigger triggers a swarming task.
//
// The provided worker isolate is used for the task.
// At completion, the swarming service will publish a message, including the provided user data, to the provided pubsub topic.
func (s *SwarmingServer) Trigger(c context.Context, worker *admin.Worker, workerIsolate, pubsubUserdata, pubsubTopic string) (string, error) {
	dims := []*swarming.SwarmingRpcsStringPair{}
	for _, d := range worker.Dimensions {
		// Extracting dimension key and value. Note that ':' may appear in the value but not the key.
		dim := strings.SplitN(d, ":", 2)
		if len(dim) != 2 {
			return "", fmt.Errorf("failed to split dimension: %q", d)
		}
		dims = append(dims, &swarming.SwarmingRpcsStringPair{Key: dim[0], Value: dim[1]})
	}
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create oauth client: %v", err)
		return "", fmt.Errorf("failed to create oauth client: %v", err)
	}
	// TODO(emso): extend the deadline in the http client transport.
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to create swarming client: %v", err)
		return "", fmt.Errorf("failed to create swarming client: %v", err)
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", s.SwarmingServerURL, swarmingBasePath)
	res, err := swarmingService.Tasks.New(&swarming.SwarmingRpcsNewTaskRequest{
		Name:           worker.Name,
		Priority:       100,
		ExpirationSecs: 21600,
		Properties: &swarming.SwarmingRpcsTaskProperties{
			Dimensions:           dims,
			ExecutionTimeoutSecs: 600,
			InputsRef: &swarming.SwarmingRpcsFilesRef{
				Isolated:       workerIsolate,
				Isolatedserver: s.IsolateServerURL,
				Namespace:      isolatedclient.DefaultNamespace,
			},
			IoTimeoutSecs: 600,
		},
		PubsubTopic:    pubsubTopic,
		PubsubUserdata: pubsubUserdata,
	}).Do()
	if err != nil {
		logging.WithError(err).Errorf(c, "failed to trigger swarming task: %v", err)
		return "", fmt.Errorf("failed to trigger swarming task: %v", err)
	}
	logging.Infof(c, "[driver] Worker triggered, ID: %q, name: %q, dimensions: %v, pubsub topic: %s", res.TaskId, worker.Name, dims, pubsubTopic)
	return res.TaskId, nil
}

// Collect collects results for a swarming task with the provided ID.
//
// The task in question should be completed before this function is called and the
// task should have isolated output.
// The isolated output and exit code of the task are returned.
func (s *SwarmingServer) Collect(c context.Context, taskID string) (string, int64, error) {
	oauthClient, err := getOAuthClient(c)
	if err != nil {
		return "", 0, fmt.Errorf("failed to create oauth client: %v", err)
	}
	swarmingService, err := swarming.New(oauthClient)
	if err != nil {
		return "", 0, fmt.Errorf("failed to create swarming client: %v", err)
	}
	swarmingService.BasePath = fmt.Sprintf("%s%s", s.SwarmingServerURL, swarmingBasePath)
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
type MockSwarmingAPI struct {
}

// Trigger is a mock function for the MockSwarmingAPI.
//
// For any testing actually using the return value, create a new mock.
func (*MockSwarmingAPI) Trigger(c context.Context, worker *admin.Worker, workerIsolate, pubsubUserdata, pubsubTopic string) (string, error) {
	return "mockmockmock", nil
}

// Collect is a mock function for the MockSwarmingAPI.
//
// For any testing actually using the return value, create a new mock.
func (*MockSwarmingAPI) Collect(c context.Context, taskID string) (string, int64, error) {
	return "mockmockmock", 0, nil
}
