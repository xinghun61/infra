// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"

	"infra/tricium/api/admin/v1"
)

// Workflow config entry for storing in datastore.
type Workflow struct {
	// The run ID for the workflow.
	ID int64 `gae:"$id"`

	// Serialized workflow config proto.
	SerializedWorkflow []byte `gae:",noindex"`
}

// WorkflowCacheAPI stores generated workflows.
type WorkflowCacheAPI interface {
	// GetWorkflow returns the stored workflow for the provided run ID.
	GetWorkflow(c context.Context, runID int64) (*admin.Workflow, error)
}

// WorkflowCache implements the WorkflowCacheAPI using Datastore.
var WorkflowCache workflowCache

type workflowCache struct{}

// GetWorkflow implements the WorkflowCacheAPI.
func (workflowCache) GetWorkflow(c context.Context, runID int64) (*admin.Workflow, error) {
	wfb := &Workflow{ID: runID}
	if err := ds.Get(c, wfb); err != nil {
		return nil, err
	}
	wf := &admin.Workflow{}
	if err := proto.Unmarshal(wfb.SerializedWorkflow, wf); err != nil {
		return nil, err
	}
	return wf, nil
}
