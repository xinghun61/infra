// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/config"
	"go.chromium.org/luci/config/server/cfgclient"
	"go.chromium.org/luci/config/server/cfgclient/textproto"

	"google.golang.org/appengine"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

// ProviderAPI supplies Tricium service and project configs.
//
// For of the functions below, the local dev server will use
// locally checked in config files under "devcfg/".
type ProviderAPI interface {
	// GetServiceConfig loads the service config from luci-config.
	GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error)

	// GetProjectConfig loads one project config for the provided project.
	GetProjectConfig(c context.Context, project string) (*tricium.ProjectConfig, error)

	// GetAllProjectConfigs fetches a map of project names to project configs.
	GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error)
}

// LuciConfigServer supplies Tricium configs stored in luci-config.
var LuciConfigServer luciConfigServer

type luciConfigServer struct {
}

// GetServiceConfig implements the ProviderAPI.
func (luciConfigServer) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	ret := &tricium.ServiceConfig{}
	cs := config.Set("services/" + serviceName(c))
	if err := cfgclient.Get(c, cfgclient.AsService, cs, "service.cfg",
		textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get service config: %v", err)
	}
	return ret, nil
}

// GetProjectConfig implements the ProviderAPI.
func (luciConfigServer) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	ret := &tricium.ProjectConfig{}
	cs := config.Set("projects/" + p)
	if err := cfgclient.Get(c, cfgclient.AsService, cs, serviceName(c)+".cfg",
		textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get project config: %v", err)
	}
	return ret, nil
}

// GetAllProjectConfigs implements the ProviderAPI.
func (luciConfigServer) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	var meta []*config.Meta
	var configs []*tricium.ProjectConfig
	if err := cfgclient.Projects(c, cfgclient.AsService, serviceName(c)+".cfg",
		textproto.Slice(&configs), &meta); err != nil {
		return nil, fmt.Errorf("failed to get all project configs: %v", err)
	}
	logging.Infof(c, "%d project configs fetched", len(configs))
	if len(meta) != len(configs) {
		return nil, fmt.Errorf("meta length (%d) doesn't match configs length", len(meta))
	}
	ret := make(map[string]*tricium.ProjectConfig, len(configs))
	for i, cfg := range configs {
		ret[meta[i].ConfigSet.Project()] = cfg
	}
	return ret, nil
}

func serviceName(c context.Context) string {
	if appengine.IsDevAppServer() {
		return common.TriciumDevServer
	}
	return info.AppID(c)
}

// MockProvider mocks the ProviderAPI interface.
//
// Tests using the return values should implement their own mock.
var MockProvider mockProvider

type mockProvider struct{}

// GetServiceConfig is part of the mock ProviderAPI interface.
func (mockProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{}, nil
}

// GetProjectConfig is part of the mock ProviderAPI interface.
func (mockProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{}, nil
}

// GetAllProjectConfigs is part of the mock ProviderAPI interface.
func (mockProvider) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	return map[string]*tricium.ProjectConfig{}, nil
}

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

type workflowCache struct {
}

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
