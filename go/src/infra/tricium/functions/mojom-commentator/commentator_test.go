// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"os"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"infra/tricium/api/v1"
)

func analyzeTestFile(t *testing.T, name string) []*tricium.Data_Comment {
	f, err := os.Open("test/src/" + name)
	if err != nil {
		t.Errorf("Failed to open %s: %v", name, err)
		return nil
	}
	defer f.Close()

	return analyzeFile(bufio.NewScanner(f), name)
}

const (
	url = "https://bit.ly/31z0aCT"

	methodError            = "This method should have a comment describing its behavior, inputs, and outputs.\n\nSee " + url + " for details."
	interfaceErrorFragment = " should have a top-level comment that at minimum describes the caller and callee and the high-level purpose.\n\nSee " + url + " for details."
)

func TestMojomCommentator(t *testing.T) {
	Convey("Analyze file with lots of mojom syntax and no errors", t, func() {
		results := analyzeTestFile(t, "good.mojom")
		So(results, ShouldBeNil)
	})

	Convey("Commented out interfaces do not count", t, func() {
		results := analyzeTestFile(t, "commented_out.mojom")
		So(results, ShouldBeNil)
	})

	Convey("Missing a method comment on an otherwise-commeneted interface", t, func() {
		results := analyzeTestFile(t, "partial_comments.mojom")
		So(results, ShouldResemble, []*tricium.Data_Comment{{
			Category:  "MojomCommentator/method",
			Message:   methodError,
			StartLine: 7,
			Path:      "partial_comments.mojom",
		}})
	})

	Convey("Missing comments on multiple interfaces and methods", t, func() {
		path := "bad.mojom"
		results := analyzeTestFile(t, path)
		So(results, ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  "MojomCommentator/interface",
				Message:   `Interface "Foo"` + interfaceErrorFragment,
				StartLine: 1,
				Path:      path,
			},
			{
				Category:  "MojomCommentator/method",
				Message:   methodError,
				StartLine: 2,
				Path:      path,
			},
			{
				Category:  "MojomCommentator/method",
				Message:   methodError,
				StartLine: 4,
				Path:      path,
			},
			{
				Category:  "MojomCommentator/interface",
				Message:   `Interface "Another"` + interfaceErrorFragment,
				StartLine: 12,
				Path:      path,
			},
			{
				Category:  "MojomCommentator/method",
				Message:   methodError,
				StartLine: 16,
				Path:      path,
			},
		})
	})
}
