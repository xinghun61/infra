// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/luci_config/common/cfgtypes"
	"github.com/luci/luci-go/luci_config/server/cfgclient"
	"github.com/luci/luci-go/luci_config/server/cfgclient/textproto"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
)

// Provider supplies Tricium service and project configs.
type Provider interface {
	GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error)
	GetProjectConfig(c context.Context, project string) (*tricium.ProjectConfig, error)
}

// LuciConfigProvider supplies Tricium configs stored in luci-config.
var LuciConfigProvider luciConfigProvider

type luciConfigProvider struct {
}

// GetServiceConfig loads the service config from luci-config.
func (luciConfigProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	ret := &tricium.ServiceConfig{}
	if err := cfgclient.Get(c, cfgclient.AsService, "services/tricium-dev", "service.cfg", textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get service config: %v", err)
	}
	return ret, nil
}

// GetProjectConfig loads the project config for the provided project from luci-config.
func (luciConfigProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	ret := &tricium.ProjectConfig{}
	if err := cfgclient.Get(c, cfgclient.AsService, cfgtypes.ConfigSet(fmt.Sprintf("projects/%s", p)), "tricium-dev.cfg", textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get project config: %v", err)
	}
	return ret, nil
}

// MockProvider mocks the Provider interface.
var MockProvider mockProvider

type mockProvider struct {
}

// GetServiceConfig is part of a mock Provider interface.
//
// Tests using the return value should implement their own mock.
func (mockProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{}, nil
}

// GetProjectConfig is part of a mock Provider interface.
//
// Tests using the return value should implement their own mock.
func (mockProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{}, nil
}

// Workflow config entry for storing in datastore.
type Workflow struct {
	ID int64 `gae:"$id"`

	// Serialized workflow config proto.
	SerializedWorkflow []byte `gae:",noindex"`
}

// WorkflowProvider provides a workflow config from a project or a run ID.
type WorkflowProvider interface {
	ReadWorkflowForRun(context.Context, int64) (*admin.Workflow, error)
}

// DatastoreWorkflowProvider provides workflow configurations from Datastore.
var DatastoreWorkflowProvider datastoreWorkflowProvider

type datastoreWorkflowProvider struct {
}

// ReadWorkflowForRun provides workflow configurations for a run ID from Datastore.
func (datastoreWorkflowProvider) ReadWorkflowForRun(c context.Context, runID int64) (*admin.Workflow, error) {
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
