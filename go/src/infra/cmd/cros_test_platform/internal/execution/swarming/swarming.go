// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swarming defines an interface for interacting with swarming.
package swarming

import (
	"context"

	swarming_api "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

// Client defines an interface used to interact with a swarming service.
// It is implemented by infra/libs/skylab/swarming.Client
type Client interface {
	CreateTask(context.Context, *swarming_api.SwarmingRpcsNewTaskRequest) (*swarming_api.SwarmingRpcsTaskRequestMetadata, error)
	GetResults(ctx context.Context, IDs []string) ([]*swarming_api.SwarmingRpcsTaskResult, error)
	GetTaskURL(taskID string) string
}
