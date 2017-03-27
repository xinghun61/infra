// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tricium

import (
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/luci-go/common/logging/memlogger"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/auth/identity"
	. "github.com/smartystreets/goconvey/convey"
)

func TestProjectIsKnown(t *testing.T) {
	Convey("Test Environment", t, func() {

		project := "playground/gerrit-tricium"
		sc := &ServiceConfig{Projects: []*ProjectDetails{{Name: project}}}

		Convey("Known project is known", func() {
			ok := ProjectIsKnown(sc, project)
			So(ok, ShouldBeTrue)
		})

		Convey("Unknown project is unknown", func() {
			ok := ProjectIsKnown(sc, "blabla")
			So(ok, ShouldBeFalse)
		})
	})
}

func TestLookupProjectDetails(t *testing.T) {
	Convey("Test Environment", t, func() {

		project := "playground/gerrit-tricium"
		sc := &ServiceConfig{Projects: []*ProjectDetails{{Name: project}}}

		Convey("Known project is known", func() {
			p := LookupProjectDetails(sc, project)
			So(p, ShouldNotBeNil)
		})

		Convey("Unknown project is unknown", func() {
			p := LookupProjectDetails(sc, "blabla")
			So(p, ShouldBeNil)
		})
	})
}

func TestCanRequest(t *testing.T) {
	Convey("Test Environment", t, func() {
		ctx := memory.Use(memlogger.Use(context.Background()))

		project := "playground/gerrit-tricium"
		okACLGroup := "tricium-playground-requesters"
		okACLUser := "user:ok@example.com"
		pc := &ProjectConfig{
			Name: project,
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

		Convey("Only users in OK ACL group can request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity:       "user:abc@example.com",
				IdentityGroups: []string{okACLGroup},
			})
			ok, err := CanRequest(ctx, pc)
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})

		Convey("User with OK ACL can request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.Identity(okACLUser),
			})
			ok, err := CanRequest(ctx, pc)
			So(err, ShouldBeNil)
			So(ok, ShouldBeTrue)
		})

		Convey("Anonymous users cannot request", func() {
			ctx = auth.WithState(ctx, &authtest.FakeState{
				Identity: identity.AnonymousIdentity,
			})
			ok, err := CanRequest(ctx, pc)
			So(err, ShouldBeNil)
			So(ok, ShouldBeFalse)
		})
	})
}

func TestLookupAnalyzer(t *testing.T) {
	Convey("Test Environment", t, func() {

		analyzer := "PyLint"
		sc := &ServiceConfig{Analyzers: []*Analyzer{{Name: analyzer}}}

		Convey("Known service analyzer is known", func() {
			a, err := LookupServiceAnalyzer(sc, analyzer)
			So(err, ShouldBeNil)
			So(a, ShouldNotBeNil)
			So(a.Name, ShouldEqual, analyzer)
		})

		Convey("Unknown service analyzer is unknown", func() {
			a, err := LookupServiceAnalyzer(sc, "blabla")
			So(err, ShouldBeNil)
			So(a, ShouldBeNil)
		})

		pc := &ProjectConfig{
			Analyzers: []*Analyzer{
				{},
			},
		}

		Convey("Analyzer without name causes error", func() {
			_, err := LookupProjectAnalyzer(pc, analyzer)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestSupportsPlatform(t *testing.T) {
	Convey("Test Environment", t, func() {

		platform := Platform_UBUNTU
		a := &Analyzer{
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

		Convey("Supported platform is supported", func() {
			ok := SupportsPlatform(a, platform)
			So(ok, ShouldBeTrue)
		})

		Convey("Unsupported platform is not supported", func() {
			ok := SupportsPlatform(a, Platform_MAC)
			So(ok, ShouldBeFalse)
		})
	})
}

func TestSupportsConfig(t *testing.T) {
	Convey("Test Environment", t, func() {

		configName := "enable"
		a := &Analyzer{
			Name: "PyLint",
			ConfigDefs: []*ConfigDef{
				{
					Name:    configName,
					Default: "all",
				},
			},
		}

		Convey("Supported config is supported", func() {
			ok := SupportsConfig(a, &Config{Name: configName})
			So(ok, ShouldBeTrue)
		})

		Convey("Unsupported config is not supported", func() {
			ok := SupportsConfig(a, &Config{Name: "blabla"})
			So(ok, ShouldBeFalse)
		})
	})
}

func TestLookupImplForPlatform(t *testing.T) {
	Convey("Test Environment", t, func() {
		platform := Platform_LINUX
		a := &Analyzer{Impls: []*Impl{{ProvidesForPlatform: platform}}}
		Convey("Impl for known platform is returned", func() {
			i := LookupImplForPlatform(a, platform)
			So(i, ShouldNotBeNil)
		})
		Convey("Impl for unknown platform returns nil", func() {
			i := LookupImplForPlatform(a, Platform_WINDOWS)
			So(i, ShouldBeNil)
		})
	})
}

func TestLookupPlatform(t *testing.T) {
	Convey("Test Environment", t, func() {
		platform := Platform_UBUNTU
		sc := &ServiceConfig{Platforms: []*Platform_Details{{Name: platform}}}
		Convey("Known platform is returned", func() {
			p := LookupPlatform(sc, platform)
			So(p, ShouldNotBeNil)
		})
		Convey("Unknown platform returns nil", func() {
			p := LookupPlatform(sc, Platform_WINDOWS)
			So(p, ShouldBeNil)
		})
	})
}

func TestGetRecipePackages(t *testing.T) {
	Convey("Test Environment", t, func() {
		// TODO(emso): test recipe packages
	})
}

func TestGetRecipeCmd(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Unknown recipe cmd returns an error", func() {
			_, err := GetRecipeCmd(&ServiceConfig{}, Platform_LINUX)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestIsValid(t *testing.T) {
	Convey("Test Environment", t, func() {

		sc := &ServiceConfig{
			Platforms: []*Platform_Details{
				{
					Name:       Platform_LINUX,
					Dimensions: []string{"pool:Default"},
				},
			},
		}

		Convey("Analyzer config without name causes error", func() {
			a := &Analyzer{}
			err := IsAnalyzerValid(a, sc)
			So(err, ShouldNotBeNil)
		})

		Convey("Analyzer with impl without platforms causes error", func() {
			a := &Analyzer{
				Name:  "PyLint",
				Impls: []*Impl{{}},
			}
			err := IsAnalyzerValid(a, sc)
			So(err, ShouldNotBeNil)
		})

		// TODO(emso): add missing tests for IsImplValid
	})
}
