// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"errors"
	"fmt"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/server/auth"
)

// ProjectIsKnown checks if the provided project is known to the Tricium service.
func ProjectIsKnown(sc *ServiceConfig, project string) bool {
	for _, p := range sc.Projects {
		if p.Name == project {
			return true
		}
	}
	return false
}

// PlatformIsSupported checks if the provided platform is supported.
func PlatformIsSupported(sc *ServiceConfig, platform string) bool {
	for _, p := range sc.Platforms {
		if p.Name == platform {
			return true
		}
	}
	return false
}

// CanRequest checks the current user can make service requests for the project.
func CanRequest(c context.Context, pc *ProjectConfig) (bool, error) {
	return checkAcls(c, pc, Acl_REQUESTER)
}

// CanRead checks the current user can read project results.
func CanRead(c context.Context, pc *ProjectConfig) (bool, error) {
	return checkAcls(c, pc, Acl_READER)
}

func checkAcls(c context.Context, pc *ProjectConfig, role Acl_Role) (bool, error) {
	var groups []string
	for _, acl := range pc.Acls {
		if acl.Role != role {
			continue
		}
		if acl.Group != "" {
			groups = append(groups, acl.Group)
		}
		if acl.Identity == string(auth.CurrentIdentity(c)) {
			return true, nil
		}
	}
	ok, err := auth.IsMember(c, groups...)
	if err != nil {
		return false, fmt.Errorf("failed to check member in group(s): %v", err)
	}
	return ok, nil
}

// LookupProjectAnalyzer looks up the given analyzer in the project config.
func LookupProjectAnalyzer(pc *ProjectConfig, analyzer string) (*Analyzer, error) {
	return lookupAnalyzer(pc.Analyzers, analyzer)
}

// LookupServiceAnalyzer looks up the given analyzer in the service config.
func LookupServiceAnalyzer(sc *ServiceConfig, analyzer string) (*Analyzer, error) {
	return lookupAnalyzer(sc.Analyzers, analyzer)
}

func lookupAnalyzer(analyzers []*Analyzer, analyzer string) (*Analyzer, error) {
	for _, a := range analyzers {
		if a.Name == "" {
			return nil, fmt.Errorf("found analyzer missing name, looking for analyze %s", analyzer)
		}
		if a.Name == analyzer {
			return a, nil
		}
	}
	return nil, nil
}

// SupportsPlatform checks if the analyzer has an implementation for the provided platform.
func SupportsPlatform(a *Analyzer, platform string) bool {
	for _, i := range a.Impls {
		for _, p := range i.Platforms {
			if p == platform {
				return true
			}
		}
	}
	return false
}

// SupportsConfig checks if the analyzer has a config def matching the provided config.
func SupportsConfig(a *Analyzer, config *Config) bool {
	for _, c := range a.ConfigDefs {
		if c.Name == config.Name {
			return true
		}
	}
	return false
}

// IsAnalyzerValid checks if the analyzer config entry is valid.
//
// A valid analyzer config entry has a name and valid impl entries.
// Note that there are more requirements for an analyzer config to be fully
// valid in a merged config, for instance, data dependencies are required.
func IsAnalyzerValid(a *Analyzer, sc *ServiceConfig) (bool, error) {
	if a.GetName() == "" {
		return false, errors.New("missing name in analyzer config")
	}
	for _, i := range a.Impls {
		ok, err := IsImplValid(i, sc)
		if !ok {
			return false, fmt.Errorf("invalid impl for analyzer %s: %v", a.Name, err)
		}
		// TODO(emso): check for duplicate impl for platform and analyzer
	}
	return true, nil
}

// IsImplValid checks if the impl entry is valid.
//
// A valid impl entry lists one or more known platforms and has either a
// recipe-based implementation, or a cmd-based implementation, but not both.
func IsImplValid(i *Impl, sc *ServiceConfig) (bool, error) {
	if len(i.Platforms) == 0 {
		return false, errors.New("missing platform for impl")
	}
	for _, p := range i.Platforms {
		if !PlatformIsSupported(sc, p) {
			return false, fmt.Errorf("unknown platform %s", p)
		}
	}
	if i.GetCmd() != nil && i.GetRecipe() != nil {
		return false, errors.New("cannot list both cmd and recipe in the same impl")
	}
	if i.GetDeadline() == 0 {
		return false, errors.New("missing deadline")
	}
	return true, nil
}

// FlattenAnalyzer flattens the impl entries in the provided analyzer.
//
// Modifies the provided analyzer.
func FlattenAnalyzer(a *Analyzer) error {
	var impls []*Impl
	for _, i := range a.Impls {
		if len(i.Platforms) == 0 {
			return fmt.Errorf("missing platform for impl for analyzer %s", a.Name)
		}
		if len(i.Platforms) <= 1 {
			// Only one platform, let's stop here and continue.
			continue
		}
		for k, p := range i.Platforms {
			if k == 0 {
				// First platform OK, continue.
				continue
			}
			// Second or more platform, flatten.
			impls = append(impls, &Impl{
				Platforms:    []string{p}, // only this platform
				CipdPackages: i.CipdPackages,
				Recipe:       i.Recipe,
				Cmd:          i.Cmd,
				Deadline:     i.Deadline,
			})
		}
		// Let this impl get the first platform (the one we skipped above).
		i.Platforms = []string{i.Platforms[0]}
	}
	// Add the new impls we found.
	a.Impls = append(a.Impls, impls...)
	return nil
}
