// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/net/context"
	"gopkg.in/yaml.v2"

	cipd "go.chromium.org/luci/cipd/client/cipd/local"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMakePackages(t *testing.T) {
	t.Parallel()

	path := func(p string) string {
		return filepath.Join(strings.Split(p, "/")...)
	}

	Convey("makePackages works", t, func() {
		Convey("for a valid directory without exclusions", func() {
			packages, err := makePackages("testdata/WalkDir", "test/prefix", nil, nil)
			So(err, ShouldBeNil)
			So(packages["mac"].Package, ShouldEqual, "test/prefix/mac")
			So(packages["ios"].Package, ShouldEqual, "test/prefix/ios")
			So(packages["mac"].Data, ShouldResemble, []cipd.PackageChunkDef{
				{VersionFile: ".xcode_versions/mac.cipd_version"},
				{File: path("A/B/b")},
				{File: path("A/B/b2")},
				{File: path("A/a")},
				{File: path("C/c")},
				{File: path("C/c2")},
				{File: path("symlink")},
			})
			So(packages["mac"].Package, ShouldEqual, "test/prefix/mac")
			So(packages["ios"].Data, ShouldResemble, []cipd.PackageChunkDef{
				{VersionFile: ".xcode_versions/ios.cipd_version"},
			})
		})

		Convey("for a valid directory with exclusions", func() {
			excludeAll := []string{"C/", "nonexistent"}
			excludeMac := []string{"A/B/b2", "C/c2"}
			packages, err := makePackages("testdata/WalkDir", "test/exclusions", excludeAll, excludeMac)
			So(err, ShouldBeNil)
			So(packages["mac"].Package, ShouldEqual, "test/exclusions/mac")
			So(packages["mac"].Data, ShouldResemble, []cipd.PackageChunkDef{
				{VersionFile: ".xcode_versions/mac.cipd_version"},
				{File: path("A/B/b")},
				{File: path("A/a")},
				{File: path("symlink")},
			})
			So(packages["ios"].Package, ShouldEqual, "test/exclusions/ios")
			So(packages["ios"].Data, ShouldResemble, []cipd.PackageChunkDef{
				{VersionFile: ".xcode_versions/ios.cipd_version"},
				{File: path("A/B/b2")},
			})
		})

		Convey("for a nonexistent directory", func() {
			_, err := makePackages("testdata/nonexistent", "", nil, nil)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestBuildCipdPackages(t *testing.T) {
	t.Parallel()

	Convey("buildCipdPackages works", t, func() {
		packages := Packages{
			"a": {Package: "path/a", Data: []cipd.PackageChunkDef{}},
			"b": {Package: "path/b", Data: []cipd.PackageChunkDef{}},
		}
		buildFn := func(p PackageSpec) error {
			name := filepath.Base(p.YamlPath)
			So(strings.HasSuffix(name, ".yaml"), ShouldBeTrue)
			name = name[:len(name)-len(".yaml")]
			data, err := ioutil.ReadFile(p.YamlPath)
			So(err, ShouldBeNil)
			var pd cipd.PackageDef
			err = yaml.Unmarshal(data, &pd)
			So(err, ShouldBeNil)
			So(pd, ShouldResemble, packages[name])
			So(pd.Package, ShouldEqual, p.Name)
			return nil
		}

		Convey("for valid package definitions", func() {
			err := buildCipdPackages(packages, buildFn)
			So(err, ShouldBeNil)
		})
	})
}

func TestPackageXcode(t *testing.T) {
	t.Parallel()

	Convey("packageXcode works", t, func() {
		var s MockSession
		ctx := useMockCmd(context.Background(), &s)

		Convey("for remote upload using default credentials", func() {
			err := packageXcode(ctx, "testdata/Xcode-new.app", "test/prefix", "", "")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 2)

			for i := 0; i < 2; i++ {
				So(s.Calls[i].Executable, ShouldEqual, "cipd")
				So(s.Calls[i].Args, ShouldContain, "create")
				So(s.Calls[i].Args, ShouldContain, "-verification-timeout")
				So(s.Calls[i].Args, ShouldContain, "60m")
				So(s.Calls[i].Args, ShouldContain, "xcode_version:TESTXCODEVERSION")
				So(s.Calls[i].Args, ShouldContain, "build_version:TESTBUILDVERSION")
				So(s.Calls[i].Args, ShouldContain, "testbuildversion")

				So(s.Calls[i].Args, ShouldNotContain, "-service-account-json")
			}
		})

		Convey("for remote upload using a service account", func() {
			err := packageXcode(ctx, "testdata/Xcode-new.app", "test/prefix", "test-sa", "")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 2)

			for i := 0; i < 2; i++ {
				So(s.Calls[i].Executable, ShouldEqual, "cipd")
				So(s.Calls[i].Args, ShouldContain, "create")
				So(s.Calls[i].Args, ShouldContain, "-verification-timeout")
				So(s.Calls[i].Args, ShouldContain, "60m")
				So(s.Calls[i].Args, ShouldContain, "xcode_version:TESTXCODEVERSION")
				So(s.Calls[i].Args, ShouldContain, "build_version:TESTBUILDVERSION")
				So(s.Calls[i].Args, ShouldContain, "testbuildversion")

				So(s.Calls[i].Args, ShouldContain, "-service-account-json")
			}
		})

		Convey("for local package creating", func() {
			// Make sure `outputDir` actually exists in testdata; otherwise the test
			// will needlessly create a directory and leave it behind.
			err := packageXcode(ctx, "testdata/Xcode-new.app", "test/prefix", "", "testdata/outdir")
			So(err, ShouldBeNil)
			So(s.Calls, ShouldHaveLength, 2)

			So(s.Calls[0].Args, ShouldContain, filepath.Join("testdata/outdir", "ios.cipd"))
			So(s.Calls[1].Args, ShouldContain, filepath.Join("testdata/outdir", "mac.cipd"))

			for i := 0; i < 2; i++ {
				So(s.Calls[i].Executable, ShouldEqual, "cipd")
				So(s.Calls[i].Args, ShouldContain, "pkg-build")

				So(s.Calls[i].Args, ShouldNotContain, "-service-account-json")
				So(s.Calls[i].Args, ShouldNotContain, "-verification-timeout")
				So(s.Calls[i].Args, ShouldNotContain, "60m")
				So(s.Calls[i].Args, ShouldNotContain, "-tag")
				So(s.Calls[i].Args, ShouldNotContain, "-ref")
			}
		})
	})
}
