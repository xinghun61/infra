// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/common/logging/memlogger"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
)

func TestProjectIsKnown(t *testing.T) {

	project := "playground/gerrit-tricium"
	sc := &ServiceConfig{Projects: []*ProjectDetails{{Name: project}}}

	Convey("Known project is known", t, func() {
		ok := ProjectIsKnown(sc, project)
		So(ok, ShouldBeTrue)
	})

	Convey("Unknown project is unknown", t, func() {
		ok := ProjectIsKnown(sc, "blabla")
		So(ok, ShouldBeFalse)
	})
}

func TestLookupProjectDetails(t *testing.T) {
	project := "playground/gerrit-tricium"
	sc := &ServiceConfig{Projects: []*ProjectDetails{{Name: project}}}

	Convey("Known project is known", t, func() {
		p := LookupProjectDetails(sc, project)
		So(p, ShouldNotBeNil)
	})

	Convey("Unknown project is unknown", t, func() {
		p := LookupProjectDetails(sc, "blabla")
		So(p, ShouldBeNil)
	})
}

func TestLookupRepoDetails(t *testing.T) {

	pc := &ProjectConfig{
		Repos: []*RepoDetails{
			{
				Source: &RepoDetails_GitRepo{
					GitRepo: &GitRepo{
						Url: "https://github.com/google/gitiles.git",
					},
				},
			},
			{
				Source: &RepoDetails_GerritProject{
					GerritProject: &GerritProject{
						Host:    "chromium.googlesource.com",
						Project: "infra/infra",
						GitUrl:  "https://chromium.googlesource.com/infra/infra.git",
					},
				},
			},
		},
	}

	Convey("Matches GerritProject when URL matches", t, func() {
		request := &AnalyzeRequest{
			Source: &AnalyzeRequest_GerritRevision{
				GerritRevision: &GerritRevision{
					GitUrl: "https://chromium.googlesource.com/infra/infra.git",
					GitRef: "refs/changes/97/12397/1",
				},
			},
		}
		So(LookupRepoDetails(pc, request), ShouldEqual, pc.Repos[1])
	})

	Convey("Matches GitRepo when URL matches", t, func() {
		request := &AnalyzeRequest{
			Source: &AnalyzeRequest_GitCommit{
				GitCommit: &GitCommit{
					Url: "https://github.com/google/gitiles.git",
					Ref: "refs/heads/master",
				},
			},
		}
		So(LookupRepoDetails(pc, request), ShouldEqual, pc.Repos[0])
	})

	Convey("Returns nil when no repo is found", t, func() {
		request := &AnalyzeRequest{
			Source: &AnalyzeRequest_GerritRevision{
				GerritRevision: &GerritRevision{
					GitUrl: "https://foo.googlesource.com/bar",
					GitRef: "refs/changes/97/197/2",
				},
			},
		}
		So(LookupRepoDetails(pc, request), ShouldBeNil)
	})
}

func TestCanRequest(t *testing.T) {
	ctx := memory.Use(memlogger.Use(context.Background()))

	okACLGroup := "tricium-playground-requesters"
	okACLUser := "user:ok@example.com"
	pc := &ProjectConfig{
		Acls: []*Acl{
			{
				Role:  Acl_REQUESTER,
				Group: okACLGroup,
			},
			{
				Role:     Acl_REQUESTER,
				Identity: okACLUser,
			},
		},
	}

	Convey("Only users in OK ACL group can request", t, func() {
		ctx = auth.WithState(ctx, &authtest.FakeState{
			Identity:       "user:abc@example.com",
			IdentityGroups: []string{okACLGroup},
		})
		ok, err := CanRequest(ctx, pc)
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})

	Convey("User with OK ACL can request", t, func() {
		ctx = auth.WithState(ctx, &authtest.FakeState{
			Identity: identity.Identity(okACLUser),
		})
		ok, err := CanRequest(ctx, pc)
		So(err, ShouldBeNil)
		So(ok, ShouldBeTrue)
	})

	Convey("Anonymous users cannot request", t, func() {
		ctx = auth.WithState(ctx, &authtest.FakeState{
			Identity: identity.AnonymousIdentity,
		})
		ok, err := CanRequest(ctx, pc)
		So(err, ShouldBeNil)
		So(ok, ShouldBeFalse)
	})
}

func TestLookupFunction(t *testing.T) {

	analyzer := "PyLint"
	sc := &ServiceConfig{
		Functions: []*Function{
			{
				Type: Function_ANALYZER,
				Name: analyzer,
			},
		},
	}

	Convey("Known service function is known", t, func() {
		f := LookupServiceFunction(sc, analyzer)
		So(f, ShouldNotBeNil)
		So(f.Name, ShouldEqual, analyzer)
	})

	Convey("Unknown service function is unknown", t, func() {
		f := LookupServiceFunction(sc, "blabla")
		So(f, ShouldBeNil)
	})

	pc := &ProjectConfig{
		Functions: []*Function{
			{},
		},
	}

	Convey("Function without name returns nil", t, func() {
		f := LookupProjectFunction(pc, analyzer)
		So(f, ShouldBeNil)
	})
}

func TestSupportsPlatform(t *testing.T) {
	platform := Platform_UBUNTU
	analyzer := &Function{
		Type: Function_ANALYZER,
		Name: "PyLint",
		Impls: []*Impl{
			{
				ProvidesForPlatform: Platform_WINDOWS,
			},
			{
				ProvidesForPlatform: platform,
			},
		},
	}

	Convey("Supported platform is supported", t, func() {
		So(SupportsPlatform(analyzer, platform), ShouldBeTrue)
	})

	Convey("Unsupported platform is not supported", t, func() {
		So(SupportsPlatform(analyzer, Platform_MAC), ShouldBeFalse)
	})
}

func TestSupportsConfig(t *testing.T) {
	configName := "enable"
	analyzer := &Function{
		Type: Function_ANALYZER,
		Name: "PyLint",
		ConfigDefs: []*ConfigDef{
			{
				Name:    configName,
				Default: "all",
			},
		},
	}

	Convey("Supported config is supported", t, func() {
		ok := SupportsConfig(analyzer, &Config{Name: configName})
		So(ok, ShouldBeTrue)
	})

	Convey("Unsupported config is not supported", t, func() {
		ok := SupportsConfig(analyzer, &Config{Name: "blabla"})
		So(ok, ShouldBeFalse)
	})
}

func TestLookupImplForPlatform(t *testing.T) {
	implForLinux := &Impl{ProvidesForPlatform: Platform_LINUX}
	implForMac := &Impl{ProvidesForPlatform: Platform_MAC}
	analyzer := &Function{
		Impls: []*Impl{
			implForLinux,
			implForMac,
		},
	}

	Convey("Impl for known platform is returned", t, func() {
		i := LookupImplForPlatform(analyzer, Platform_LINUX)
		So(i, ShouldEqual, implForLinux)
	})

	Convey("Impl for any platform returns first", t, func() {
		// In this case, there is no implementation in
		// the list that is explicitly for any platform;
		// we return the first implementation.
		i := LookupImplForPlatform(analyzer, Platform_ANY)
		So(i, ShouldEqual, implForLinux)
	})

	Convey("Impl for unknown platform returns nil", t, func() {
		i := LookupImplForPlatform(analyzer, Platform_WINDOWS)
		So(i, ShouldBeNil)
	})

	implForAny := &Impl{ProvidesForPlatform: Platform_ANY}
	analyzer = &Function{
		Impls: []*Impl{
			implForLinux,
			implForAny,
		},
	}

	Convey("Impl for 'any' platform is used if present", t, func() {
		// In this case, there is an implementation in
		// the list that is explicitly for any platform;
		// we return the 'any' implementation.
		i := LookupImplForPlatform(analyzer, Platform_ANY)
		So(i, ShouldEqual, implForAny)
	})
}

func TestLookupPlatform(t *testing.T) {
	platform := Platform_UBUNTU
	sc := &ServiceConfig{Platforms: []*Platform_Details{{Name: platform}}}

	Convey("Known platform is returned", t, func() {
		p := LookupPlatform(sc, platform)
		So(p, ShouldNotBeNil)
	})

	Convey("Unknown platform returns nil", t, func() {
		p := LookupPlatform(sc, Platform_WINDOWS)
		So(p, ShouldBeNil)
	})
}

func TestGetRecipePackages(t *testing.T) {
	// TODO(emso): test recipe packages
}

func TestGetRecipeCmd(t *testing.T) {
	Convey("Unknown recipe cmd returns an error", t, func() {
		_, err := GetRecipeCmd(&ServiceConfig{}, Platform_LINUX)
		So(err, ShouldNotBeNil)
	})
}

func TestValidateFunction(t *testing.T) {

	sc := &ServiceConfig{
		Platforms: []*Platform_Details{
			{
				Name:       Platform_LINUX,
				Dimensions: []string{"pool:Default"},
				HasRuntime: true,
			},
			{
				Name:       Platform_IOS,
				Dimensions: []string{"pool:Default"},
				HasRuntime: false,
			},
		},
	}

	Convey("Function without type is invalid", t, func() {
		f := &Function{
			Name:     "PyLint",
			Needs:    Data_FILES,
			Provides: Data_RESULTS,
		}
		So(ValidateFunction(f, sc), ShouldNotBeNil)
	})

	Convey("Function without name is invalid", t, func() {
		f := &Function{
			Type:     Function_ANALYZER,
			Needs:    Data_FILES,
			Provides: Data_RESULTS,
		}
		So(ValidateFunction(f, sc), ShouldNotBeNil)
	})

	Convey("Analyzer function must return results", t, func() {
		f := &Function{
			Type:     Function_ANALYZER,
			Name:     "ConfusedAnalyzer",
			Needs:    Data_FILES,
			Provides: Data_CLANG_DETAILS,
		}
		So(ValidateFunction(f, sc), ShouldNotBeNil)
		f.Provides = Data_RESULTS
		So(ValidateFunction(f, sc), ShouldBeNil)
	})

	Convey("Isolator functions must not return results", t, func() {
		f := &Function{
			Type:     Function_ISOLATOR,
			Name:     "ConfusedIsolator",
			Needs:    Data_FILES,
			Provides: Data_RESULTS,
		}
		So(ValidateFunction(f, sc), ShouldNotBeNil)
		f.Provides = Data_CLANG_DETAILS
		So(ValidateFunction(f, sc), ShouldBeNil)
	})

	Convey("Function with impl without platforms is invalid", t, func() {
		f := &Function{
			Type:  Function_ANALYZER,
			Name:  "PyLint",
			Impls: []*Impl{{}},
		}
		So(ValidateFunction(f, sc), ShouldNotBeNil)
	})
}

func TestValidateImpl(t *testing.T) {

	sc := &ServiceConfig{
		Platforms: []*Platform_Details{
			{
				Name:       Platform_UBUNTU,
				Dimensions: []string{"pool:Default"},
				HasRuntime: true,
			},
			{
				Name:       Platform_ANDROID,
				HasRuntime: false,
			},
		},
	}

	anyType := &Data_TypeDetails{
		IsPlatformSpecific: false,
	}

	Convey("Example of a valid non-platform-specific Impl", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_UBUNTU,
			Impl:            &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline:        60,
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldBeNil)
	})

	Convey("Runtime platform of Impl must exist in service config", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_IOS,
			Impl:            &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline:        60,
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldNotBeNil)
	})

	Convey("Runtime platform of Impl must have a runtime", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_ANDROID,
			Impl:            &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline:        60,
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldNotBeNil)
	})

	Convey("Runtime platform must be included in Impl", t, func() {
		impl := &Impl{
			Impl:     &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline: 60,
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldNotBeNil)
	})

	Convey("Impl must have deadline specified", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_UBUNTU,
			Impl:            &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldNotBeNil)
	})

	Convey("Impl must have cmd or recipe specified", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_UBUNTU,
			Deadline:        60,
		}
		So(validateImpl(impl, sc, anyType, anyType), ShouldNotBeNil)
	})

	Convey("Example of a valid platform-specific Impl", t, func() {
		impl := &Impl{
			RuntimePlatform:     Platform_UBUNTU,
			NeedsForPlatform:    Platform_ANDROID,
			ProvidesForPlatform: Platform_ANDROID,
			Impl:                &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline:            60,
		}
		needsType := &Data_TypeDetails{
			Type:               Data_CLANG_DETAILS,
			IsPlatformSpecific: true,
		}
		providesType := &Data_TypeDetails{
			Type:               Data_RESULTS,
			IsPlatformSpecific: true,
		}
		So(validateImpl(impl, sc, needsType, providesType), ShouldBeNil)
	})

	Convey("If type is platform-specific, platforms must be specified", t, func() {
		impl := &Impl{
			RuntimePlatform: Platform_UBUNTU,
			Impl:            &Impl_Cmd{Cmd: &Cmd{Exec: "hello"}},
			Deadline:        60,
		}
		needsType := &Data_TypeDetails{
			Type:               Data_CLANG_DETAILS,
			IsPlatformSpecific: true,
		}
		providesType := &Data_TypeDetails{
			Type:               Data_RESULTS,
			IsPlatformSpecific: true,
		}
		So(validateImpl(impl, sc, needsType, providesType), ShouldNotBeNil)
	})
}
