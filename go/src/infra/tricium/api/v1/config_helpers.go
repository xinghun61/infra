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

// LookupProjectDetails lookups up the project details entry for the provided project.
//
// Unknown projects results in nil.
func LookupProjectDetails(sc *ServiceConfig, project string) *ProjectDetails {
	for _, p := range sc.Projects {
		if p.Name == project {
			return p
		}
	}
	return nil
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

// LookupImplForPlatform returns the first impl providing data for the provided platform.
func LookupImplForPlatform(a *Analyzer, platform Platform_Name) *Impl {
	for _, i := range a.Impls {
		if i.ProvidesForPlatform == platform {
			return i
		}
	}
	return nil
}

// LookupPlatform returns the first platform matching the provided platform name.
func LookupPlatform(sc *ServiceConfig, platform Platform_Name) *Platform_Details {
	for _, p := range sc.Platforms {
		if p.Name == platform {
			return p
		}
	}
	return nil
}

// SupportsPlatform checks if the provided analyzer has an implementation providing data for the provided platform.
func SupportsPlatform(a *Analyzer, platform Platform_Name) bool {
	for _, i := range a.Impls {
		if i.ProvidesForPlatform == platform {
			return true
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

// GetRecipePackages returns the base service recipe packages for recipe-based implementations.
func GetRecipePackages(sc *ServiceConfig, platform Platform_Name) ([]*CipdPackage, error) {
	if len(sc.RecipePackages) == 0 {
		return nil, errors.New("service recipe packages missing")
	}
	// TODO(emso): adjust packages for platform.
	return sc.RecipePackages, nil
}

// GetRecipeCmd returns the base service command for recipe-based implementations.
func GetRecipeCmd(sc *ServiceConfig, platform Platform_Name) (*Cmd, error) {
	if sc.GetRecipeCmd() == nil {
		return nil, errors.New("service recipe command missing")
	}
	// TODO(emso): Adjust for platform?
	return &Cmd{
		Exec: sc.RecipeCmd.Exec,
		Args: sc.RecipeCmd.Args,
	}, nil
}

// IsAnalyzerValid checks if the analyzer config entry is valid.
//
// A valid analyzer config entry has a name, valid deps and valid impl entries.
// Note that there are more requirements for an analyzer config to be fully
// valid in a merged config, for instance, data dependencies are required.
func IsAnalyzerValid(a *Analyzer, sc *ServiceConfig) error {
	if a.GetName() == "" {
		return errors.New("missing name in analyzer config")
	}
	pm := make(map[Platform_Name]bool)
	for _, i := range a.Impls {
		needs, err := LookupDataTypeDetails(sc, a.Needs)
		if err != nil {
			return errors.New("analyzer has impl that needs unknown data type")
		}
		provides, err := LookupDataTypeDetails(sc, a.Provides)
		if err != nil {
			return errors.New("analyzer has impl that provides unknown data type")
		}
		ok, err := IsImplValid(i, sc, needs, provides)
		if !ok {
			return fmt.Errorf("invalid impl for analyzer %s: %v", a.Name, err)
		}
		if i.ProvidesForPlatform == Platform_ANY {
			continue
		}
		if _, ok := pm[i.ProvidesForPlatform]; ok {
			return fmt.Errorf("multiple impl providing data for platform %v", i.ProvidesForPlatform)
		}
		pm[i.ProvidesForPlatform] = true
	}
	return nil
}

// IsImplValid checks if the impl entry is valid.
//
// A valid impl entry has a valid runtime platform, one with a runtime, specifies platforms
// for data-dependencies when needed, has a cmd or recipe based implementation, and a deadline.
func IsImplValid(i *Impl, sc *ServiceConfig, needs *Data_TypeDetails, provides *Data_TypeDetails) (bool, error) {
	if i.GetRuntimePlatform() == Platform_ANY {
		return false, errors.New("must provide runtime platform for impl")
	}
	runtime := LookupPlatform(sc, i.GetRuntimePlatform())
	if runtime == nil {
		return false, fmt.Errorf("impl using unknown runtime platform: %v", i.RuntimePlatform)
	}
	if !runtime.GetHasRuntime() {
		return false, errors.New("must provide a runtime platform that has a runtime")
	}
	if needs.GetIsPlatformSpecific() && i.GetNeedsForPlatform() == Platform_ANY {
		return false, errors.New("must specify platform for needed platform-specific data type")
	}
	if provides.GetIsPlatformSpecific() && i.GetProvidesForPlatform() == Platform_ANY {
		return false, errors.New("must specify platform for provided platform-specific data type")
	}
	if i.GetCmd() == nil && i.GetRecipe() == nil {
		return false, errors.New("must include either command or recipe in impl")
	}
	if i.GetDeadline() == 0 {
		return false, errors.New("missing deadline")
	}
	return true, nil
}

// LookupDataTypeDetails looks up data type details for a given type from the provided service config.
func LookupDataTypeDetails(sc *ServiceConfig, dt Data_Type) (*Data_TypeDetails, error) {
	for _, d := range sc.GetDataDetails() {
		if d.Type == dt {
			return d, nil
		}
	}
	return nil, fmt.Errorf("data type undefined: %v", dt)
}
