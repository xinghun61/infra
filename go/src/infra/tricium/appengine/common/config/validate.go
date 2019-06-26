// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"
	"strings"

	"go.chromium.org/luci/common/errors"

	tricium "infra/tricium/api/v1"
)

// Validate validates the provided project config using the provided service
// config.
//
// They are validated together because a project config may contain a selection
// which is valid or invalid depending on the service config.
//
// Returns an error if invalid, or nil if valid.
func Validate(sc *tricium.ServiceConfig, pc *tricium.ProjectConfig) error {
	if sc.SwarmingServer == "" {
		return errors.Reason("missing swarming server URL in service config").Err()
	}
	if sc.IsolateServer == "" {
		return errors.Reason("missing isolate server URL in service config").Err()
	}
	if sc.BuildbucketServerHost == "" {
		return errors.Reason("missing buildbucket server host in service config").Err()
	}
	if pc.SwarmingServiceAccount == "" {
		return errors.Reason("missing swarming service account for project: %+v", pc).Err()
	}
	functions, err := mergeSelectedFunctions(sc, pc)
	if err != nil {
		return errors.Annotate(err, "failed to merge functions").Err()
	}
	for _, s := range pc.Selections {
		name := s.Function
		f := functions[name]
		if err := tricium.ValidateFunction(f, sc); err != nil {
			return errors.Annotate(err, "function is not valid").Err()
		}
		if strings.Contains(s.Platform.String(), "_") {
			// Underscore is used as a separator character in worker names.
			return errors.Reason("platform %q should not contain underscore character", s.Platform).Err()
		}
		if !tricium.SupportsPlatform(f, s.Platform) {
			return errors.Reason("no support for platform %s by function %s", s.Platform, name).Err()
		}
		for _, c := range s.Configs {
			if !tricium.SupportsConfig(f, c) {
				return errors.Reason("no support for config %s by function %s", c.Name, name).Err()
			}
		}
	}
	return nil
}

// Merges all function definitions for selections in the project config.
func mergeSelectedFunctions(sc *tricium.ServiceConfig, pc *tricium.ProjectConfig) (map[string]*tricium.Function, error) {
	functions := map[string]*tricium.Function{}
	for _, s := range pc.Selections {
		// Get merged function definition.
		name := s.Function
		if _, ok := functions[name]; !ok {
			sf := tricium.LookupFunction(sc.Functions, name)
			pf := tricium.LookupFunction(pc.Functions, name)
			f, err := mergeFunction(name, sc, sf, pf)
			if err != nil {
				return nil, err
			}
			functions[name] = f
		}
	}
	return functions, nil
}

// mergeFunction merges the provided service and project function definitions.
//
// In merging, the following override rules are applied:
// - existence of project path_filters fully replaces any service path_filters.
// - project impl for platform fully replaces service impl for the same platform.
// - project owner and component from project overrides service if set.
//
// While merging, mergeFunctions also validates the functions.
//
// Possible errors include:
//  - change of data dependency in service config is not allowed.
//  - project and service config functions must have the same type.
func mergeFunction(function string, sc *tricium.ServiceConfig, sf, pf *tricium.Function) (*tricium.Function, error) {
	if sf == nil && pf == nil {
		return nil, errors.Reason("unknown function %s", function).Err()
	}
	res := &tricium.Function{Name: function}
	if sf != nil {
		if err := tricium.ValidateFunction(sf, sc); err != nil {
			return nil, errors.Reason("invalid service function config for %s: %v", function, err).Err()
		}
		if sf.GetNeeds() == tricium.Data_NONE || sf.GetProvides() == tricium.Data_NONE {
			return nil, errors.Reason("service function config must have data dependencies, function: %s", function).Err()
		}
		res.Type = sf.Type
		res.Needs = sf.Needs
		res.Provides = sf.Provides
		res.PathFilters = sf.PathFilters
		res.Owner = sf.Owner
		res.MonorailComponent = sf.MonorailComponent
		res.ConfigDefs = sf.ConfigDefs
		res.Impls = sf.Impls
	}
	if pf != nil {
		if sf != nil &&
			(sf.Type != pf.Type) {
			return nil, fmt.Errorf("cannot merge functions of different type, name: %s, service type: %s, project type: %s",
				pf.Name, sf.Type, pf.Type)
		}
		res.Type = pf.Type
		if sf != nil &&
			(pf.GetNeeds() != tricium.Data_NONE && pf.GetNeeds() != sf.GetNeeds() ||
				pf.GetProvides() != tricium.Data_NONE && pf.GetProvides() != sf.GetProvides()) {
			return nil, errors.Reason("change of service function data dependencies not allowed, function: %s", function).Err()
		}
		if sf == nil {
			if pf.GetNeeds() == tricium.Data_NONE || pf.GetProvides() == tricium.Data_NONE {
				return nil, errors.Reason("project function config is missing data dependencies, function: %s", function).Err()
			}
			res.Needs = pf.Needs
			res.Provides = pf.Provides
		}
		// Add service deps to project entry for validation check.
		// These deps are used to check validity of impls and when
		// there are service deps they are inherited by the project
		// entry.
		if sf != nil {
			pf.Needs = sf.Needs
			pf.Provides = sf.Provides
		}
		if err := tricium.ValidateFunction(pf, sc); err != nil {
			return nil, errors.Reason("invalid project function config for %s: %v", function, err).Err()
		}
		if pf.GetPathFilters() != nil {
			res.PathFilters = pf.PathFilters
		}
		if pf.GetOwner() != "" {
			res.Owner = pf.Owner
		}
		if pf.GetMonorailComponent() != "" {
			res.MonorailComponent = pf.MonorailComponent
		}
		if sf != nil {
			res.ConfigDefs = mergeConfigDefs(sf.ConfigDefs, pf.ConfigDefs)
			res.Impls = mergeImpls(sf.Impls, pf.Impls)
		} else {
			res.ConfigDefs = pf.ConfigDefs
			res.Impls = pf.Impls
		}
	}
	return res, nil
}

// mergeConfigDefs merges the service function config defs with the project
// function config defs.
//
// The project config defs can override service config defs with the same name.
func mergeConfigDefs(scd []*tricium.ConfigDef, pcd []*tricium.ConfigDef) []*tricium.ConfigDef {
	configs := map[string]*tricium.ConfigDef{}
	for _, cd := range scd {
		configs[cd.Name] = cd
	}
	for _, cd := range pcd {
		configs[cd.Name] = cd
	}
	res := []*tricium.ConfigDef{}
	for _, v := range configs {
		res = append(res, v)
	}
	return res
}

// mergeImpls merges the service function implementations with the project
// function implementations.
//
// All provided impl entries are assumed to be valid. The project
// implementations can override the service implementations for the same
// platform.
func mergeImpls(sci []*tricium.Impl, pci []*tricium.Impl) []*tricium.Impl {
	impls := map[tricium.Platform_Name]*tricium.Impl{}
	for _, i := range sci {
		impls[i.ProvidesForPlatform] = i
	}
	for _, i := range pci {
		impls[i.ProvidesForPlatform] = i
	}
	res := []*tricium.Impl{}
	for _, v := range impls {
		res = append(res, v)
	}
	return res
}
