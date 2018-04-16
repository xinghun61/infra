// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCLAndPatchSetNumberFunctions(t *testing.T) {
	Convey("Extracts patch set number from valid ref", t, func() {
		So(PatchSetNumber("refs/changes/43/6543/7"), ShouldEqual, "7")
		So(PatchSetNumber("refs/changes/45/12345/12"), ShouldEqual, "12")
	})

	Convey("Extracts CL number from valid ref", t, func() {
		So(CLNumber("refs/changes/43/6543/7"), ShouldEqual, "6543")
		So(CLNumber("refs/changes/45/12345/12"), ShouldEqual, "12345")
	})

	Convey("Both numbers can be extracted in one invocation", t, func() {
		cl, patch := ExtractCLPatchSetNumbers("refs/changes/45/12345/12")
		So(cl, ShouldEqual, "12345")
		So(patch, ShouldEqual, "12")
	})

	Convey("When input format is invalid, empty strings are returned", t, func() {
		cl, patch := ExtractCLPatchSetNumbers("refs/changes/1111/1")
		So(cl, ShouldEqual, "")
		So(patch, ShouldEqual, "")
	})

	Convey("Given invalid input, returns empty string", t, func() {
		So(PatchSetNumber("foorefs/changes/45/12345/7bar"), ShouldEqual, "")
		So(PatchSetNumber("refs/changes/45/12345"), ShouldEqual, "")
		So(PatchSetNumber("refs/changes/45/12345/"), ShouldEqual, "")
		So(PatchSetNumber(""), ShouldEqual, "")
	})

	Convey("Given invalid input, returns empty string", t, func() {
		So(CLNumber("foorefs/changes/45/12345/7bar"), ShouldEqual, "")
		So(CLNumber("refs/changes/45/12345"), ShouldEqual, "")
		So(CLNumber("refs/changes/45/12345/"), ShouldEqual, "")
		So(CLNumber(""), ShouldEqual, "")
	})
}

func TestComposeGerritURL(t *testing.T) {
	Convey("gerritURL with well-formed Gerrit change ref", t, func() {
		So(
			GerritURL("https://chromium-review.googlesource.com", "refs/changes/10/12310/3"),
			ShouldEqual, "https://chromium-review.googlesource.com/c/12310/3")
	})

	Convey("with badly-formed ref returns empty string", t, func() {
		So(GerritURL("foo.com", "xxrefs/changes/10/12310/3xx"), ShouldEqual, "")
		So(GerritURL("foo.com", "refs/changes/123/4"), ShouldEqual, "")
	})
}
