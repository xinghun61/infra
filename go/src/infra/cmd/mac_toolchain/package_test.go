// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"path/filepath"
	"strings"
	"testing"

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

func TestUploadCipdPackages(t *testing.T) {
	t.Parallel()

	Convey("uploadCipdPackages works", t, func() {
		packages := Packages{
			"a": {Package: "path/a", Data: []cipd.PackageChunkDef{}},
			"b": {Package: "path/b", Data: []cipd.PackageChunkDef{}},
		}
		uploadFn := func(p PackageSpec) error {
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
			err := uploadCipdPackages(packages, uploadFn)
			So(err, ShouldBeNil)
		})
	})
}
