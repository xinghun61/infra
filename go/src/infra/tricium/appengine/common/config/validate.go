// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package config

import (
	"fmt"

	"infra/tricium/api/v1"
)

// Validate validates the provided project config using the provided service config.
func Validate(sc *tricium.ServiceConfig, pc *tricium.ProjectConfig) (*tricium.ProjectConfig, error) {
	if sc.SwarmingServer == "" {
		return nil, fmt.Errorf("missing swarming server URL in service config")
	}
	if sc.IsolateServer == "" {
		return nil, fmt.Errorf("missing isolate server URL in service config")
	}
	pd := tricium.LookupProjectDetails(sc, pc.Name)
	if pd == nil {
		return nil, fmt.Errorf("unknown project, project: %s", pc.Name)
	}
	if pd.SwarmingServiceAccount == "" {
		return nil, fmt.Errorf("missing swarming service account for project, project: %s", pc.Name)
	}
	res := &tricium.ProjectConfig{
		Name:       pc.Name,
		Acls:       pc.Acls,
		Selections: pc.Selections,
	}
	functions := map[string]*tricium.Function{}
	for _, s := range pc.Selections {
		// Get merged function definition.
		if _, ok := functions[s.Function]; !ok {
			sca := tricium.LookupServiceFunction(sc, s.Function)
			pca := tricium.LookupProjectFunction(pc, s.Function)
			f, err := mergeFunctions(s.Function, sc, sca, pca)
			if err != nil {
				return nil, err
			}
			functions[s.Function] = f
			res.Functions = append(res.Functions, f)
		}
		if err := tricium.IsFunctionValid(functions[s.Function], sc); err != nil {
			return nil, fmt.Errorf("function is not valid: %v", err)
		}
		if !tricium.SupportsPlatform(functions[s.Function], s.Platform) {
			return nil, fmt.Errorf("no support for platform %s by function %s", s.Platform, s.Function)
		}
		for _, c := range s.Configs {
			if !tricium.SupportsConfig(functions[s.Function], c) {
				return nil, fmt.Errorf("no support for config %s by function %s", c.Name, s.Function)
			}
		}
	}
	for _, v := range functions {
		res.Functions = append(res.Functions, v)
	}
	return res, nil
}

// mergeFunctions merges the provided service and project function configs.
//
// In merging, the following override rules are applied:
// - existence of project path_filters fully replace any service path_filters.
// - project impl for platform fully replace service impl for the same platform
// - project owner, component
// Errors:
//  - change of data dependency in service config not allowed
func mergeFunctions(function string, sc *tricium.ServiceConfig, sa, pa *tricium.Function) (*tricium.Function, error) {
	// TODO(emso): extract nil checks an similar out of this function and let if focus on only merging
	if sa == nil && pa == nil {
		return nil, fmt.Errorf("unknown function %s", function)
	}
	res := &tricium.Function{Name: function}
	if sa != nil {
		if err := tricium.IsFunctionValid(sa, sc); err != nil {
			return nil, fmt.Errorf("invalid service function config for %s: %v", function, err)
		}
		if sa.GetNeeds() == tricium.Data_NONE || sa.GetProvides() == tricium.Data_NONE {
			return nil, fmt.Errorf("service function config must have data dependencies, function: %s", function)
		}
		res.Type = sa.Type
		res.Needs = sa.Needs
		res.Provides = sa.Provides
		res.PathFilters = sa.PathFilters
		res.Owner = sa.Owner
		res.MonorailComponent = sa.MonorailComponent
		res.ConfigDefs = sa.ConfigDefs
		res.Impls = sa.Impls
	}
	if pa != nil {
		if sa != nil &&
			(sa.Type != pa.Type) {
			return nil, fmt.Errorf("cannot merge functions of different type, name: %s, service type: %s, project type: %s",
				pa.Name, sa.Type, pa.Type)
		}
		res.Type = pa.Type
		if sa != nil &&
			(pa.GetNeeds() != tricium.Data_NONE && pa.GetNeeds() != sa.GetNeeds() ||
				pa.GetProvides() != tricium.Data_NONE && pa.GetProvides() != sa.GetProvides()) {
			return nil, fmt.Errorf("change of service function data dependencies not allowed, function: %s", function)
		}
		if sa == nil {
			if pa.GetNeeds() == tricium.Data_NONE || pa.GetProvides() == tricium.Data_NONE {
				return nil, fmt.Errorf("project function config is missing data dependencies, function: %s", function)
			}
			res.Needs = pa.Needs
			res.Provides = pa.Provides
		}
		// Add service deps to project entry for validation check. These deps are used to check validity of impls and when
		// there are service deps they are inherited by the project entry.
		if sa != nil {
			pa.Needs = sa.Needs
			pa.Provides = sa.Provides
		}
		if err := tricium.IsFunctionValid(pa, sc); err != nil {
			return nil, fmt.Errorf("invalid project function config for %s: %v", function, err)
		}
		if pa.GetPathFilters() != nil {
			res.PathFilters = pa.PathFilters
		}
		if pa.GetOwner() != "" {
			res.Owner = pa.Owner
		}
		if pa.GetMonorailComponent() != "" {
			res.MonorailComponent = pa.MonorailComponent
		}
		if sa != nil {
			res.ConfigDefs = mergeConfigDefs(sa.ConfigDefs, pa.ConfigDefs)
			res.Impls = mergeImpls(sa.Impls, pa.Impls)
		} else {
			res.ConfigDefs = pa.ConfigDefs
			res.Impls = pa.Impls
		}
	}
	return res, nil
}

// mergeConfigDefs merges the service function config defs with the project function config defs.
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

// mergeImpls merges the service function implementations with the project function implementations.
//
// All provided impl entries are assumed to be valid.
// The project implementations can override the service implementations for the same platform.
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
