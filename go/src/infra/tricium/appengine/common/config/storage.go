// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"

	ds "go.chromium.org/gae/service/datastore"

	tricium "infra/tricium/api/v1"
)

// projectConfig contains a Tricium project config for one config.
type projectConfig struct {
	Name          string  `gae:"$id"`
	Parent        *ds.Key `gae:"$parent"`
	Revision      string
	ProjectConfig tricium.ProjectConfig
}

// serviceConfig is the single service config for this Tricium instance.
type serviceConfig struct {
	ID            int64   `gae:"$id"`
	Parent        *ds.Key `gae:"$parent"`
	Revision      string
	ServiceConfig tricium.ServiceConfig
}

// By putting all config entities under one common parent, this makes it so
// that all configs are part of one entity group, so reads of all project
// configs in one query can be strongly consistent. See https://goo.gl/YgmiQF.
func rootKey(c context.Context) *ds.Key {
	return ds.MakeKey(c, "configRoot", 1)
}

// getAllProjectConfigs retrieves stored project configs.
func getAllProjectConfigs(c context.Context) (map[string]*tricium.ProjectConfig, error) {
	var storedConfigs []*projectConfig
	q := ds.NewQuery("projectConfig").Ancestor(rootKey(c))
	if err := ds.GetAll(c, q, &storedConfigs); err != nil {
		return nil, err
	}
	configs := map[string]*tricium.ProjectConfig{}
	for _, stored := range storedConfigs {
		configs[stored.Name] = &stored.ProjectConfig
	}
	return configs, nil
}

// getStoredProjectConfigRevisions retrieves revisions of project configs.
//
// If there are no project configs stored yet, this will return an empty map.
func getStoredProjectConfigRevisions(c context.Context) (map[string]string, error) {
	var storedConfigs []*projectConfig
	q := ds.NewQuery("projectConfig").Ancestor(rootKey(c))
	if err := ds.GetAll(c, q, &storedConfigs); err != nil {
		return nil, err
	}
	revisions := map[string]string{}
	for _, stored := range storedConfigs {
		revisions[stored.Name] = stored.Revision
	}
	return revisions, nil
}

// getProjectConfig retrieves one project config by name.
func getProjectConfig(c context.Context, name string) (*tricium.ProjectConfig, error) {
	stored := &projectConfig{Name: name, Parent: rootKey(c)}
	if err := ds.Get(c, stored); err != nil {
		return nil, err
	}
	return &stored.ProjectConfig, nil
}

// getServiceConfig retrieves the stored service config.
func getServiceConfig(c context.Context) (*tricium.ServiceConfig, error) {
	stored := &serviceConfig{ID: 1, Parent: rootKey(c)}
	if err := ds.Get(c, stored); err != nil {
		return nil, err
	}
	return &stored.ServiceConfig, nil
}

// getStoredServiceConfigRevision retrieves the current service config revision.
//
// If there's no service config stored yet, empty string shall be returned.
func getStoredServiceConfigRevision(c context.Context) (string, error) {
	stored := &serviceConfig{ID: 1, Parent: rootKey(c)}
	err := ds.Get(c, stored)
	if err == ds.ErrNoSuchEntity {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return stored.Revision, nil
}

// setProjectConfig stores a project config by name.
func setProjectConfig(c context.Context, name string, revision string, pc *tricium.ProjectConfig) error {
	return ds.Put(c, &projectConfig{
		Name:          name,
		Parent:        rootKey(c),
		Revision:      revision,
		ProjectConfig: *pc,
	})
}

// setServiceConfig set the stored service config.
func setServiceConfig(c context.Context, revision string, sc *tricium.ServiceConfig) error {
	return ds.Put(c, &serviceConfig{
		ID:            1,
		Parent:        rootKey(c),
		Revision:      revision,
		ServiceConfig: *sc,
	})
}

// deleteProjectConfigs removes project configs with the given names.
func deleteProjectConfigs(c context.Context, names []string) error {
	var keys []*ds.Key
	for _, name := range names {
		keys = append(keys, ds.NewKey(c, "projectConfig", name, 0, rootKey(c)))
	}
	return ds.Delete(c, keys)
}
