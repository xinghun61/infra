// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/common/data/stringset"
)

func TestHelperFunctions(t *testing.T) {
	// TODO(crbug.com/904007): Remove tests for isSkipped after adding
	// .gitattributes files.
	Convey("isSkipped skips generated expectations files", t, func() {
		So(isSkipped("infra/recipes/recipes/foo.expected/bar.json"), ShouldBeTrue)
		So(isSkipped("infra/recipes/recipes/foo.expected/bar.json"), ShouldBeTrue)
		So(isSkipped("third_party/blink/web_tests/a/b/foo-expected.txt"), ShouldBeTrue)
	})

	Convey("isSkipped skips generated proto files", t, func() {
		So(isSkipped("infra/infra/project/protos/foo_pb2.py"), ShouldBeTrue)
		So(isSkipped("infra/infra/project/protos/foo.pb.go"), ShouldBeTrue)
		So(isSkipped("infra/recipes/recipes/foo.expected/bar.json"), ShouldBeTrue)
		So(isSkipped("third_party/blink/web_tests/a/b/foo-expected.txt"), ShouldBeTrue)
	})

	Convey("isSkipped skips third_party files except those in blink", t, func() {
		So(isSkipped("third_party/foo/a/b/bar.cc"), ShouldBeTrue)
		So(isSkipped("third_party/blink/renderer/bar.cc"), ShouldBeFalse)
	})

	Convey("isSkipped returns false for paths that shouldn't match", t, func() {
		So(isSkipped("a/b/c/foo.cc"), ShouldBeFalse)
		So(isSkipped("README.md"), ShouldBeFalse)
		So(isSkipped("foothird_partybar.md"), ShouldBeFalse)
		So(isSkipped("x/expected.json"), ShouldBeFalse)
		So(isSkipped("x/expected.txt"), ShouldBeFalse)
		So(isSkipped("x/expected.html"), ShouldBeFalse)
		So(isSkipped("x/pb.go"), ShouldBeFalse)
	})

	Convey("possibleGitattributesPaths lists all relevant paths", t, func() {
		So(
			possibleGitattributesPaths([]string{"one/two/foo.c"}),
			ShouldResemble,
			[]string{
				".gitattributes",
				"one/.gitattributes",
				"one/two/.gitattributes",
			})
	})

	Convey("possibleGitattributesPaths works for multiple paths", t, func() {
		So(
			possibleGitattributesPaths([]string{
				"one/bar.c",
				"one/two/foo.c",
				"one/two/foo.h",
				"one/other/x.txt",
			}),
			ShouldResemble,
			[]string{
				".gitattributes",
				"one/.gitattributes",
				"one/other/.gitattributes",
				"one/two/.gitattributes",
			})
	})

	Convey("ancestorDirectories gives the union of all ancestor dir paths", t, func() {
		So(ancestorDirectories([]string{"a/b/c/foo.proto"}),
			ShouldResemble,
			stringset.NewFromSlice("", "a", "a/b", "a/b/c"))
		So(ancestorDirectories([]string{"a/b/c/foo.proto", "x/y/foo.c"}),
			ShouldResemble,
			stringset.NewFromSlice("", "a", "a/b", "a/b/c", "x", "x/y"))
	})

	Convey("splitNull splits null-separated and terminated strings", t, func() {
		So(splitNull("f 1\x00"), ShouldResemble, []string{"f 1"})
		So(splitNull("f 1\x00f 2\x00"), ShouldResemble, []string{"f 1", "f 2"})
	})
}
