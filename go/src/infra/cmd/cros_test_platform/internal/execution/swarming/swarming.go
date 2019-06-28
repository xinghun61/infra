// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming defines an interface for interacting with swarming.
package swarming

import (
	"context"

	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/swarming/proto/jsonrpc"
)

// Client defines an interface used to interact with a swarming service.
// It is implemented by infra/libs/skylab/swarming.Client
type Client interface {
	CreateTask(context.Context, *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error)
	GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error)
	GetTaskURL(taskID string) string
	GetTaskOutputs(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskOutput, error)
}

// UnfinishedTaskStates indicate swarming states that correspond to non-final
// tasks.
var UnfinishedTaskStates = map[jsonrpc.TaskState]bool{
	jsonrpc.TaskState_PENDING: true,
	jsonrpc.TaskState_RUNNING: true,
}

// AsTaskState converts the string swarming task state into enum representation.
func AsTaskState(state string) (jsonrpc.TaskState, error) {
	val, ok := jsonrpc.TaskState_value[state]
	if !ok {
		return jsonrpc.TaskState_INVALID, errors.Reason("invalid task state %s", state).Err()
	}
	return jsonrpc.TaskState(val), nil
}
