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

func TestPlatformIsSupported(t *testing.T) {
	Convey("Test Environment", t, func() {

		platform := "Ubuntu14.04-x86-64"
		sc := &ServiceConfig{Platforms: []*Platform{{Name: platform}}}

		Convey("Supported platform is supported", func() {
			ok := PlatformIsSupported(sc, platform)
			So(ok, ShouldBeTrue)
		})

		Convey("Unknown platform is not supported", func() {
			ok := PlatformIsSupported(sc, "blabla")
			So(ok, ShouldBeFalse)
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

		platform := "Ubuntu14.04-x86-64"
		a := &Analyzer{
			Name: "PyLint",
			Impls: []*Impl{
				{
					Platforms: []string{"Windows"},
				},
				{
					Platforms: []string{platform},
				},
			},
		}

		Convey("Supported platform is supported", func() {
			ok := SupportsPlatform(a, platform)
			So(ok, ShouldBeTrue)
		})

		Convey("Unsupported platform is not supported", func() {
			ok := SupportsPlatform(a, "Mac")
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

func TestIsValid(t *testing.T) {
	Convey("Test Environment", t, func() {

		sc := &ServiceConfig{
			Platforms: []*Platform{
				{
					Name:       "Linux",
					Dimensions: []string{"pool:Default"},
				},
			},
		}

		Convey("Analyzer config without name causes error", func() {
			a := &Analyzer{}
			ok, err := IsAnalyzerValid(a, sc)
			So(ok, ShouldBeFalse)
			So(err, ShouldNotBeNil)
		})

		Convey("Analyzer with impl without platforms causes error", func() {
			a := &Analyzer{
				Name:  "PyLint",
				Impls: []*Impl{{}},
			}
			ok, err := IsAnalyzerValid(a, sc)
			So(ok, ShouldBeFalse)
			So(err, ShouldNotBeNil)
		})

		// TODO(emso): add missing tests for IsImplValid
	})
}

func TestFlattenAnalyzer(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("Flattens implementation fields", func() {
			p1 := "Linux-32"
			p2 := "Linux-64"
			analyzer := &Analyzer{
				Impls: []*Impl{
					{
						Platforms: []string{
							p1,
							p2,
						},
						Cmd: &Cmd{
							Exec: "echo",
							Args: []string{
								"hello",
							},
						},
						Deadline: 3200,
					},
				},
			}
			FlattenAnalyzer(analyzer)
			So(len(analyzer.Impls), ShouldEqual, 2)
			So(len(analyzer.Impls[0].Platforms), ShouldEqual, 1)
			So(len(analyzer.Impls[1].Platforms), ShouldEqual, 1)
			So(analyzer.Impls[0].Platforms[0], ShouldEqual, p1)
			So(analyzer.Impls[1].Platforms[0], ShouldEqual, p2)
		})
	})
}
