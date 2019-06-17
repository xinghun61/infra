// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"

	tricium "infra/tricium/api/v1"
)

// ProviderAPI supplies Tricium service and project configs.
type ProviderAPI interface {
	// GetServiceConfig loads the service config from luci-config.
	GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error)

	// GetProjectConfig loads one project config for the provided project.
	GetProjectConfig(c context.Context, project string) (*tricium.ProjectConfig, error)

	// GetAllProjectConfigs fetches a map of project names to project configs.
	GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error)
}

// LuciConfigServer provides configs fetched from luci-config.
//
// The configs are fetched in a cron job and stored in datastore.
var LuciConfigServer configProvider

type configProvider struct{}

// GetServiceConfig implements the ProviderAPI.
func (configProvider) GetServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	return getServiceConfig(c)
}

// GetProjectConfig implements the ProviderAPI.
func (configProvider) GetProjectConfig(c context.Context, p string) (*tricium.ProjectConfig, error) {
	return getProjectConfig(c, p)
}

// GetAllProjectConfigs implements the ProviderAPI.
func (configProvider) GetAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	return getAllProjectConfigs(c)
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
