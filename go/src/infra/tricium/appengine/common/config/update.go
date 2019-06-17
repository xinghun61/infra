// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"context"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	luciConfig "go.chromium.org/luci/config"

	tricium "infra/tricium/api/v1"
	"infra/tricium/appengine/common"
)

// UpdateAllConfigs updates all configs.
//
// This includes updating and removing project configs when necessary and
// updating the service config if necessary.
//
// TODO(crbug.com/915375) Check for overlapping repos specified between projects.
func UpdateAllConfigs(c context.Context) error {
	// Update service config first which is needed for project config validation.
	if err := updateServiceConfig(c); err != nil {
		return err
	}
	sc, err := getServiceConfig(c)
	if err != nil {
		return err
	}
	return updateAllProjectConfigs(c, sc)
}

func updateAllProjectConfigs(c context.Context, sc *tricium.ServiceConfig) error {
	// List projects to update and delete.
	fetchedRevisions, err := fetchProjectConfigRevisions(c)
	if err != nil {
		return err
	}
	storedRevisions, err := getStoredProjectConfigRevisions(c)
	if err != nil {
		return err
	}
	changed := listChanged(storedRevisions, fetchedRevisions)
	dead := listDead(storedRevisions, fetchedRevisions)

	// Update changed projects in parallel.
	return parallel.FanOutIn(func(taskC chan<- func() error) {
		for _, name := range changed {
			name := name
			taskC <- func() error {
				return updateProjectConfig(c, sc, name)
			}
		}
		taskC <- func() error {
			return deleteProjectConfigs(c, dead)
		}
	})
}

func listChanged(stored, fetched map[string]string) []string {
	var changed []string
	for name, fr := range fetched {
		sr := stored[name]
		if fr != sr {
			changed = append(changed, name)
		}
	}
	return changed
}

func listDead(stored, fetched map[string]string) []string {
	var dead []string
	for name := range stored {
		if _, ok := fetched[name]; !ok {
			dead = append(dead, name)
		}
	}
	return dead
}

// updateProjectConfig updates, validates, and stores one project config.
func updateProjectConfig(c context.Context, sc *tricium.ServiceConfig, name string) error {
	pc, revision, err := fetchProjectConfig(c, name)
	if err != nil {
		return err
	}
	if err = Validate(sc, pc); err != nil {
		logging.Warningf(c, `Project %q config invalid: %v`, name, err)
		return err
	}
	logging.Fields{
		"revision": revision,
		"project":  name,
	}.Infof(c, "Found new project config.")
	return setProjectConfig(c, name, revision, pc)
}

// updateServiceConfig updates and stores a new service config.
func updateServiceConfig(c context.Context) error {
	fetchedRevision, err := fetchServiceConfigRevision(c)
	if err != nil {
		return err
	}
	storedRevision, err := getStoredServiceConfigRevision(c)
	if err != nil {
		return err
	}
	if fetchedRevision == storedRevision {
		return nil
	}
	sc, newRevision, err := fetchServiceConfig(c)
	if err != nil {
		return err
	}
	logging.Fields{
		"revision": newRevision,
	}.Infof(c, "Found new service config.")
	return setServiceConfig(c, newRevision, sc)
}

// fetchProjectConfigRevisions fetches a list of project revisions.
//
// This makes a request to the luci-config service. Fetching only
// revisions allows us to specify that we only need metadata in
// the call to GetProjectConfigs, which should be make the fetch faster.
func fetchProjectConfigRevisions(c context.Context) (map[string]string, error) {
	cfgs, err := fetchProjectConfigMeta(c)
	if err != nil {
		return nil, errors.Annotate(err, "while fetching project config revisions").Err()
	}
	logging.Infof(c, "Got config revisions for %d projects.", len(cfgs))
	revisions := map[string]string{}
	for _, cfg := range cfgs {
		revisions[cfg.ConfigSet.Project()] = cfg.Revision
	}
	return revisions, nil
}

// fetchProjectConfig fetches a single project config.
func fetchProjectConfig(c context.Context, name string) (*tricium.ProjectConfig, string, error) {
	set := luciConfig.ProjectSet(name)
	cfg, err := fetchConfig(c, set, common.AppID(c)+".cfg", false)
	if err != nil {
		return nil, "", errors.Annotate(err, "fetching config; set %q", set).Err()
	}
	pc := &tricium.ProjectConfig{}

	if err := proto.UnmarshalText(cfg.Content, pc); err != nil {
		return nil, "", errors.Annotate(err, "unmarshaling config; set %q", set).Err()
	}
	return pc, cfg.Revision, nil
}

func fetchServiceConfigRevision(c context.Context) (string, error) {
	set := luciConfig.ServiceSet(common.AppID(c))
	cfg, err := fetchConfig(c, set, "service.cfg", true)
	if err != nil {
		return "", errors.Annotate(err, "fetching config revision; set %q", set).Err()
	}
	return cfg.Revision, nil
}

func fetchServiceConfig(c context.Context) (*tricium.ServiceConfig, string, error) {
	set := luciConfig.ServiceSet(common.AppID(c))
	cfg, err := fetchConfig(c, set, "service.cfg", false)
	if err != nil {
		return nil, "", errors.Annotate(err, "fetching config; set %q", set).Err()
	}
	sc := &tricium.ServiceConfig{}
	if err := proto.UnmarshalText(cfg.Content, sc); err != nil {
		return nil, "", errors.Annotate(err, "unmarshaling config; set %q", set).Err()
	}
	return sc, cfg.Revision, nil
}

func fetchConfig(c context.Context, set luciConfig.Set, path string, metaOnly bool) (*luciConfig.Config, error) {
	service := getConfigService(c)
	if service == nil {
		return nil, errors.New("no config service")
	}
	return service.GetConfig(c, set, path, metaOnly)
}

func fetchProjectConfigMeta(c context.Context) ([]luciConfig.Config, error) {
	service := getConfigService(c)
	if service == nil {
		return nil, errors.New("no config service")
	}
	return service.GetProjectConfigs(c, common.AppID(c)+".cfg", true)
}

// configInterfaceKey is used for storing the config interface in context.
var configInterfaceKey = "configInterface"

// WithConfigService sets a config interface in the context.
func WithConfigService(c context.Context, iface luciConfig.Interface) context.Context {
	return context.WithValue(c, &configInterfaceKey, iface)
}

// getConfigService returns a luciConfig.Interface from the context.
func getConfigService(c context.Context) luciConfig.Interface {
	if iface, ok := c.Value(&configInterfaceKey).(luciConfig.Interface); ok {
		return iface
	}
	return nil
}
