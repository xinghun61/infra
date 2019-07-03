// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming implements a client for creating skylab-swarming tasks and
// getting their results.
package swarming

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"time"

	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"google.golang.org/api/googleapi"
)

// Client is a swarming client for creating tasks and waiting for their results.
type Client struct {
	SwarmingService *swarming_api.Service
	server          string
}

// New creates a new Client.
func New(ctx context.Context, h *http.Client, server string) (*Client, error) {
	service, err := newSwarmingService(ctx, h, server)
	if err != nil {
		return nil, err
	}
	c := &Client{
		SwarmingService: service,
		server:          server,
	}
	return c, nil
}

const swarmingAPISuffix = "_ah/api/swarming/v1/"

func newSwarmingService(ctx context.Context, h *http.Client, server string) (*swarming_api.Service, error) {
	s, err := swarming_api.New(h)
	if err != nil {
		return nil, errors.Annotate(err, "create swarming client").Err()
	}

	s.BasePath = server + swarmingAPISuffix
	return s, nil
}

// CreateTask creates a swarming task based on the given request,
// retrying transient errors.
func (c *Client) CreateTask(ctx context.Context, req *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error) {
	var resp *swarming_api.SwarmingRpcsTaskRequestMetadata
	createTask := func() error {
		var err error
		resp, err = c.SwarmingService.Tasks.New(req).Context(ctx).Do()
		return err
	}

	if err := callWithRetries(ctx, createTask); err != nil {
		return nil, err
	}
	return resp, nil
}

// GetResults gets results for the tasks with given IDs,
// retrying transient errors.
func (c *Client) GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results := make([]*swarming_api.SwarmingRpcsTaskResult, len(IDs))
	for i, ID := range IDs {
		var r *swarming_api.SwarmingRpcsTaskResult
		getResult := func() error {
			var err error
			r, err = c.SwarmingService.Task.Result(ID).Context(ctx).Do()
			return err
		}
		if err := callWithRetries(ctx, getResult); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("get swarming result for task %s", ID)).Err()
		}
		results[i] = r
	}
	return results, nil
}

// GetResultsForTags gets results for tasks that match all the given tags,
// retrying transient errors.
func (c *Client) GetResultsForTags(ctx context.Context, tags []string) ([]*swarming_api.SwarmingRpcsTaskResult, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	var results *swarming_api.SwarmingRpcsTaskList
	getResults := func() error {
		var err error
		results, err = c.SwarmingService.Tasks.List().Tags(tags...).Context(ctx).Do()
		return err
	}
	if err := callWithRetries(ctx, getResults); err != nil {
		return nil, errors.Annotate(err, fmt.Sprintf("get swarming result for tags %s", tags)).Err()
	}

	return results.Items, nil
}

// GetRequests gets the task requests for the given task IDs,
// retrying transient errors.
func (c *Client) GetRequests(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskRequest, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	requests := make([]*swarming_api.SwarmingRpcsTaskRequest, len(IDs))
	for i, ID := range IDs {
		var request *swarming_api.SwarmingRpcsTaskRequest
		getRequest := func() error {
			var err error
			request, err = c.SwarmingService.Task.Request(ID).Context(ctx).Do()
			return err
		}
		if err := callWithRetries(ctx, getRequest); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("rerun task %s", ID)).Err()
		}
		requests[i] = request
	}
	return requests, nil
}

// GetTaskState gets the state of the given task,
// retrying transient errors.
func (c *Client) GetTaskState(ctx context.Context, ID string) (*swarming_api.SwarmingRpcsTaskStates, error) {
	var result *swarming_api.SwarmingRpcsTaskStates
	getState := func() error {
		var err error
		result, err = c.SwarmingService.Tasks.GetStates().TaskId(ID).Context(ctx).Do()
		return err
	}
	if err := callWithRetries(ctx, getState); err != nil {
		return nil, errors.Annotate(err, fmt.Sprintf("get task state for task ID %s", ID)).Err()
	}
	return result, nil
}

// GetTaskOutputs gets the task outputs for the given IDs,
// retrying transient errors.
func (c *Client) GetTaskOutputs(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskOutput, error) {
	ctx, cf := context.WithTimeout(ctx, 60*time.Second)
	defer cf()
	results := make([]*swarming_api.SwarmingRpcsTaskOutput, len(IDs))
	for i, ID := range IDs {
		var result *swarming_api.SwarmingRpcsTaskOutput
		getResult := func() error {
			var err error
			result, err = c.SwarmingService.Task.Stdout(ID).Context(ctx).Do()
			return err
		}
		if err := callWithRetries(ctx, getResult); err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf("get swarming stdout for task %s", ID)).Err()
		}
		results[i] = result
	}
	return results, nil
}

// GetTaskURL gets a URL for the task with the given ID.
func (c *Client) GetTaskURL(taskID string) string {
	return TaskURL(c.server, taskID)
}

var retryableCodes = map[int]bool{
	http.StatusInternalServerError: true, // 500
	http.StatusBadGateway:          true, // 502
	http.StatusServiceUnavailable:  true, // 503
	http.StatusGatewayTimeout:      true, // 504
	http.StatusInsufficientStorage: true, // 507
}

func retryParams() retry.Iterator {
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay:   500 * time.Millisecond,
			Retries: 5,
		},
		Multiplier: 2,
	}
}

func tagErrIfTransient(err error) error {
	if errIsTransient(err) {
		return transient.Tag.Apply(err)
	}
	return err
}

func errIsTransient(err error) bool {
	if err == nil {
		return false
	}
	if e, ok := err.(net.Error); ok && e.Temporary() {
		return true
	}
	if e, ok := err.(*googleapi.Error); ok && retryableCodes[e.Code] {
		return true
	}
	return false
}

// callWithRetries calls the given function, retrying transient swarming
// errors, with swarming-appropriate backoff and delay.
func callWithRetries(ctx context.Context, f func() error) error {
	taggedFunc := func() error {
		return tagErrIfTransient(f())
	}
	return retry.Retry(ctx, transient.Only(retryParams), taggedFunc, nil)
}

// TaskURL returns a URL to inspect a task with the given ID.
func TaskURL(swarmingService string, taskID string) string {
	return fmt.Sprintf("%stask?id=%s", swarmingService, taskID)
}
