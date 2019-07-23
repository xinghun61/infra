// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package manifest

import (
	"path/filepath"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestManifest(t *testing.T) {
	t.Parallel()

	Convey("Reading empty", t, func() {
		m, err := Read(strings.NewReader(``), "some/dir")
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{})
	})

	Convey("Not yaml", t, func() {
		_, err := Read(strings.NewReader(`im not a YAML`), "")
		So(err, ShouldErrLike, "unmarshal errors")
	})

	Convey("Resolving contextdir", t, func() {
		m, err := Read(
			strings.NewReader(`contextdir: ../../../blarg/`),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			ContextDir: filepath.FromSlash("root/1/blarg"),
		})
	})

	Convey("Deriving contextdir from dockerfile", t, func() {
		m, err := Read(
			strings.NewReader(`dockerfile: ../../../blarg/Dockerfile`),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			Dockerfile: filepath.FromSlash("root/1/blarg/Dockerfile"),
			ContextDir: filepath.FromSlash("root/1/blarg"),
		})
	})

	Convey("Resolving imagepins", t, func() {
		m, err := Read(
			strings.NewReader(`imagepins: ../../../blarg/pins.yaml`),
			filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m, ShouldResemble, &Manifest{
			ImagePins: filepath.FromSlash("root/1/blarg/pins.yaml"),
		})
	})

	Convey("Empty build step", t, func() {
		_, err := Read(strings.NewReader(`{"build": [
			{"dest": "zzz"}
		]}`), "")
		So(err, ShouldErrLike, "bad build step #1: unrecognized or empty")
	})

	Convey("Ambiguous build step", t, func() {
		_, err := Read(strings.NewReader(`{"build": [
			{"copy": "zzz", "go_binary": "zzz"}
		]}`), "")
		So(err, ShouldErrLike, "bad build step #1: ambiguous")
	})

	Convey("Defaults in CopyBuildStep", t, func() {
		m, err := Read(strings.NewReader(`{"build": [
			{"copy": "../../../blarg/zzz"}
		]}`), filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(m.Build, ShouldHaveLength, 1)
		So(m.Build[0].Dest, ShouldEqual, "zzz")
		So(m.Build[0].Concrete(), ShouldResemble, &CopyBuildStep{
			Copy: filepath.FromSlash("root/1/blarg/zzz"),
		})
	})

	Convey("Defaults in GoBuildStep", t, func() {
		m, err := Read(strings.NewReader(`{"build": [
			{"go_binary": "go.pkg/some/tool"}
		]}`), filepath.FromSlash("root/1/2/3/4"))
		So(err, ShouldBeNil)
		So(err, ShouldBeNil)
		So(m.Build, ShouldHaveLength, 1)
		So(m.Build[0].Dest, ShouldEqual, "tool")
		So(m.Build[0].Concrete(), ShouldResemble, &GoBuildStep{
			GoBinary: "go.pkg/some/tool",
		})
	})
}
