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
	analyzers := map[string]*tricium.Analyzer{}
	for _, s := range pc.Selections {
		// Get merged analyzer definition.
		if _, ok := analyzers[s.Analyzer]; !ok {
			sca, err := tricium.LookupServiceAnalyzer(sc, s.Analyzer)
			if err != nil {
				return nil, fmt.Errorf("failed to lookup analyzer %s in service config: %v", s.Analyzer, err)
			}
			pca, err := tricium.LookupProjectAnalyzer(pc, s.Analyzer)
			if err != nil {
				return nil, fmt.Errorf("failed to lookup analyzer %s in project config: %v", s.Analyzer, err)
			}
			a, err := mergeAnalyzers(s.Analyzer, sc, sca, pca)
			if err != nil {
				return nil, err
			}
			analyzers[s.Analyzer] = a
			res.Analyzers = append(res.Analyzers, a)
		}
		if err := tricium.IsAnalyzerValid(analyzers[s.Analyzer], sc); err != nil {
			return nil, fmt.Errorf("analyzer is not valid: %v", err)
		}
		if !tricium.SupportsPlatform(analyzers[s.Analyzer], s.Platform) {
			return nil, fmt.Errorf("no support for platform %s by analyzer %s", s.Platform, s.Analyzer)
		}
		for _, c := range s.Configs {
			if !tricium.SupportsConfig(analyzers[s.Analyzer], c) {
				return nil, fmt.Errorf("no support for config %s by analyzer %s", c.Name, s.Analyzer)
			}
		}
	}
	for _, v := range analyzers {
		res.Analyzers = append(res.Analyzers, v)
	}
	return res, nil
}

// mergeAnalyzers merges the provided service and project analyzer configs.
//
// In merging, the following override rules are applied:
// - existence of project path_filters fully replace any service path_filters.
// - project impl for platform fully replace service impl for the same platform
// - project owner, component
// Errors:
//  - change of data dependency in service config not allowed
func mergeAnalyzers(analyzer string, sc *tricium.ServiceConfig, sa, pa *tricium.Analyzer) (*tricium.Analyzer, error) {
	// TODO(emso): extract nil checks an similar out of this function and let if focus on only merging
	if sa == nil && pa == nil {
		return nil, fmt.Errorf("unknown analyzer %s", analyzer)
	}
	res := &tricium.Analyzer{Name: analyzer}
	if sa != nil {
		if err := tricium.IsAnalyzerValid(sa, sc); err != nil {
			return nil, fmt.Errorf("invalid service analyzer config for %s: %v", analyzer, err)
		}
		if sa.GetNeeds() == tricium.Data_NONE || sa.GetProvides() == tricium.Data_NONE {
			return nil, fmt.Errorf("service analyzer config must have data dependencies, analyzer: %s", analyzer)
		}
		res.Needs = sa.Needs
		res.Provides = sa.Provides
		res.PathFilters = sa.PathFilters
		res.Owner = sa.Owner
		res.Component = sa.Component
		res.ConfigDefs = sa.ConfigDefs
		res.Impls = sa.Impls
	}
	if pa != nil {
		if sa != nil &&
			(pa.GetNeeds() != tricium.Data_NONE && pa.GetNeeds() != sa.GetNeeds() ||
				pa.GetProvides() != tricium.Data_NONE && pa.GetProvides() != sa.GetProvides()) {
			return nil, fmt.Errorf("change of service analyzer data dependencies not allowed, analyzer: %s", analyzer)
		}
		if sa == nil {
			if pa.GetNeeds() == tricium.Data_NONE || pa.GetProvides() == tricium.Data_NONE {
				return nil, fmt.Errorf("project analyzer config is missing data dependencies, analyzer: %s", analyzer)
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
		if err := tricium.IsAnalyzerValid(pa, sc); err != nil {
			return nil, fmt.Errorf("invalid project analyzer config for %s: %v", analyzer, err)
		}
		if pa.GetPathFilters() != nil {
			res.PathFilters = pa.PathFilters
		}
		if pa.GetOwner() != "" {
			res.Owner = pa.Owner
		}
		if pa.GetComponent() != "" {
			res.Component = pa.Component
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

// mergeConfigDefs merges the service analyzer config defs with the project analyzer config defs.
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

// mergeImpls merges the service analyzer implementations with the project analyzer implementations.
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
