// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/luci_config/common/cfgtypes"
	"github.com/luci/luci-go/luci_config/server/cfgclient"
	"github.com/luci/luci-go/luci_config/server/cfgclient/textproto"

	"github.com/luci/gae/service/info"

	"golang.org/x/net/context"
)

// getSettings loads the settings from the config service.
func getSettings(c context.Context, fallback bool) (*settings.Settings, error) {
	configSet, path := cfgclient.CurrentServiceConfigSet(c), "settings.cfg"

	// Fetch configuration from config service.
	var s settings.Settings
	if err := cfgclient.Get(c, cfgclient.AsService, configSet, path, textproto.Message(&s), nil); err != nil {
		if fallback {
			log.Fields{
				log.ErrorKey: err,
				"configSet":  configSet,
				"path":       path,
			}.Errorf(c, "Failed to get application settings; using defaults.")
			return &settings.Settings{}, nil
		}
		return nil, errors.Annotate(err, "").InternalReason(
			"failed to load settings: configSet(%q)/path(%q)", configSet, path).Err()
	}

	// Validate
	if s.BuildbucketHost == "" {
		return nil, errors.New("missing required setting: BuildBucket Host")
	}
	return &s, nil
}

// getProjectConfig loads the settings from the config service.
func getProjectConfig(c context.Context, p cfgtypes.ProjectName) (*settings.ProjectConfig, error) {
	configSet, path := cfgtypes.ProjectConfigSet(p), fmt.Sprintf("%s.cfg", info.AppID(c))

	// Fetch configuration from config service.
	var pc settings.ProjectConfig
	if err := cfgclient.Get(c, cfgclient.AsUser, configSet, path, textproto.Message(&pc), nil); err != nil {
		return nil, errors.Annotate(err, "").InternalReason(
			"failed to load config path %q from project %q, configSet(%q)", path, p, configSet).Err()
	}
	return &pc, nil
}

// getAllProjectConfigs loads the settings from the config service.
func getAllProjectConfigs(c context.Context) (map[cfgtypes.ProjectName]*settings.ProjectConfig, error) {
	// Get all project configs.
	path := fmt.Sprintf("%s.cfg", info.AppID(c))
	var (
		pcfgs []*settings.ProjectConfig
		metas []*cfgclient.Meta
		merr  errors.MultiError
	)

	if err := cfgclient.Projects(c, cfgclient.AsUser, path, textproto.Slice(&pcfgs), &metas); err != nil {
		switch et := err.(type) {
		case errors.MultiError:
			merr = et // Will selectively load into map in success path.

		default:
			return nil, errors.Annotate(err, "failed to load project configs at %q", path).Err()
		}
	}

	// Load the configurations into the output map. If any config failed to load,
	// log its failure and continue.
	projMap := make(map[cfgtypes.ProjectName]*settings.ProjectConfig, len(pcfgs))
	for i, pcfg := range pcfgs {
		// Did we get an error loading this particular config?
		if merr != nil && merr[i] != nil {
			log.Fields{
				log.ErrorKey: merr[i],
				"configSet":  metas[i].ConfigSet,
				"path":       metas[i].Path,
			}.Errorf(c, "Failed to load project config (ignoring).")
			continue
		}

		projName, _, _ := metas[i].ConfigSet.SplitProject()
		if projName == "" {
			log.Fields{
				"configSet": metas[i].ConfigSet,
			}.Errorf(c, "Failed to parse project name from config set.")
			continue
		}
		projMap[projName] = pcfg
	}

	// Unmarshal each project config. If any fails, we will just ignore it.
	return projMap, nil
}
