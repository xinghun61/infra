// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	ds "github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/luci_config/common/cfgtypes"
	"github.com/luci/luci-go/luci_config/server/cfgclient"
	"github.com/luci/luci-go/luci_config/server/cfgclient/textproto"

	"google.golang.org/appengine"

	"infra/tricium/api/admin/v1"
	"infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

// ProviderAPI supplies Tricium service and project configs.
type ProviderAPI interface {
	// GetServiceConfig loads the service config from luci-config.
	//
	// The Tricium dev server is used for a the local dev server together with
	// local checked in config files under 'devcfg/'.
	GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error)

	// GetProjectConfig loads the project config for the provided project from luci-config.
	//
	// Local checked in files are used on the dev server.
	GetProjectConfig(c context.Context, project string) (*tricium.ProjectConfig, error)
}

// LuciConfigServer supplies Tricium configs stored in luci-config.
var LuciConfigServer luciConfigServer

type luciConfigServer struct {
}

// GetServiceConfig implements the ProviderAPI.
func (luciConfigServer) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	ret := &tricium.ServiceConfig{}
	service := common.TriciumDevServer
	if !appengine.IsDevAppServer() {
		service = info.AppID(c)
	}
	if err := cfgclient.Get(c, cfgclient.AsService, cfgtypes.ConfigSet(fmt.Sprintf("services/%s", service)),
		"service.cfg", textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get service config: %v", err)
	}
	return ret, nil
}

// GetProjectConfig implements the ProviderAPI.
func (luciConfigServer) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	service := common.TriciumDevServer
	if !appengine.IsDevAppServer() {
		service = info.AppID(c)
	}
	ret := &tricium.ProjectConfig{}
	if err := cfgclient.Get(c, cfgclient.AsService, cfgtypes.ConfigSet(fmt.Sprintf("projects/%s", p)),
		fmt.Sprintf("%s.cfg", service), textproto.Message(ret), nil); err != nil {
		return nil, fmt.Errorf("failed to get project config: %v", err)
	}
	return ret, nil
}

// MockProvider mocks the ProviderAPI interface.
var MockProvider mockProvider

type mockProvider struct {
}

// GetServiceConfig is part of the mock ProviderAPI interface.
//
// Tests using the return value should implement their own mock.
func (mockProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return &tricium.ServiceConfig{}, nil
}

// GetProjectConfig is part of the mock ProviderAPI interface.
//
// Tests using the return value should implement their own mock.
func (mockProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return &tricium.ProjectConfig{}, nil
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
