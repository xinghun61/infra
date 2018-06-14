// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"

	"bufio"
	. "github.com/smartystreets/goconvey/convey"
	"infra/tricium/api/v1"
	"strings"
)

func TestCheckSpaceMix(t *testing.T) {
	Convey("Finds tab + single space mix", t, func() {
		So(checkSpaceMix("test.file", "\t code", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   1,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "         code",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with spaces",
				},
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "\tcode",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with tabs",
				},
			},
		})
	})

	Convey("Finds tab + multiple space mix", t, func() {
		So(checkSpaceMix("test.file", "\t  code", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   2,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "          code",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     7,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with spaces",
				},
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "\tcode",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     7,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with tabs",
				},
			},
		})
	})

	Convey("Finds space + tab mix", t, func() {
		So(checkSpaceMix("test.file", " \tcode", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   1,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "         code",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with spaces",
				},
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "\tcode",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with tabs",
				},
			},
		})
	})

	Convey("Finds other whitespace mix", t, func() {
		So(checkSpaceMix("test.file", "\t\v\f...", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/SpaceMix",
			Message:   "Found mix of white space characters",
			StartLine: 1,
			EndLine:   1,
			StartChar: 0,
			EndChar:   2,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "        ...",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with spaces",
				},
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "\t...",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     6,
						},
					},
					Description: "Replace all whitespace at the beginning of the line with tabs",
				},
			},
		})
	})

	Convey("Produces no comment for mid-line space mix", t, func() {
		So(checkSpaceMix("test.file", "+ \tcode", 1), ShouldBeNil)
	})

	Convey("Produces no comment in Makefile", t, func() {
		So(checkSpaceMix("Makefile", "\t  some code", 1), ShouldBeNil)
	})

	Convey("Produces no comment in makefile with extension", t, func() {
		So(checkSpaceMix("my.mk", "\t  some code", 1), ShouldBeNil)
	})

	Convey("Produces no comment in patch file", t, func() {
		So(checkSpaceMix("my.patch", " \t\tsome code", 1), ShouldBeNil)
	})
}

func TestCheckTrailingSpace(t *testing.T) {
	Convey("Finds single trailing space", t, func() {
		So(checkTrailingSpace("test.file", "code ", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/TrailingSpace",
			Message:   "Found trailing space",
			StartLine: 1,
			EndLine:   1,
			StartChar: 4,
			EndChar:   4,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "code",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     4,
						},
					},
					Description: "Get rid of trailing space",
				},
			},
		})
	})

	Convey("Finds multiple trailing spaces", t, func() {
		So(checkTrailingSpace("test.file", "code  ", 1), ShouldResemble, &tricium.Data_Comment{
			Path:      "test.file",
			Category:  "Spacey/TrailingSpace",
			Message:   "Found trailing space",
			StartLine: 1,
			EndLine:   1,
			StartChar: 4,
			EndChar:   5,
			Suggestions: []*tricium.Data_Suggestion{
				{
					Replacements: []*tricium.Data_Replacement{
						{
							Replacement: "code",
							Path:        "test.file",
							StartLine:   1,
							EndLine:     1,
							StartChar:   0,
							EndChar:     5,
						},
					},
					Description: "Get rid of trailing space",
				},
			},
		})
	})

	Convey("Produces no comment in blacklisted file types", t, func() {
		So(checkTrailingSpace("my.patch", " ", 1), ShouldBeNil)
		So(checkTrailingSpace("my.pdf", " ", 1), ShouldBeNil)
	})
}

func TestCheckTrailingLines(t *testing.T) {
	Convey("Finds trailing lines at the end of a file", t, func() {
		So(analyzeFile(bufio.NewScanner(strings.NewReader("some code\nsome more code\n\n\n")),
			"file.path"), ShouldResemble, []*tricium.Data_Comment{
			{
				Category:  "Spacey/TrailingLines",
				Message:   "Found empty line(s) at the end of the file",
				Path:      "file.path",
				StartLine: 3,
				EndLine:   5,
			},
		})
	})
}

func TestMergingSimilarComments(t *testing.T) {
	Convey("Merges multiple similar comments (TrailingSpace) together into one", t, func() {
		inputComments := []*tricium.Data_Comment{
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 1,
				EndLine:   1,
				StartChar: 4,
				EndChar:   5,
			},
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 2,
				EndLine:   2,
				StartChar: 4,
				EndChar:   5,
			},
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 1,
				EndLine:   1,
				StartChar: 3,
				EndChar:   99,
			},
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 9,
				EndLine:   9,
				StartChar: 43,
				EndChar:   51,
			},
		}
		expectedComments := []*tricium.Data_Comment{{
			Path:     "test.file",
			Category: "Spacey/TrailingSpace",
			Message:  "Found 4 Spacey/TrailingSpace warnings in this file",
		}}

		organizedComments := organizeCommentsByCategory(inputComments)
		So(mergeComments(organizedComments, "test.file"), ShouldResemble, expectedComments)
	})

	Convey("Keeps similar comments separate if their number of occurrences is below set limit", t, func() {
		inputComments := []*tricium.Data_Comment{
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 1,
				EndLine:   1,
				StartChar: 4,
				EndChar:   5,
			},
			{
				Path:      "test.file",
				Category:  "Spacey/TrailingSpace",
				Message:   "Found trailing space",
				StartLine: 2,
				EndLine:   2,
				StartChar: 4,
				EndChar:   5,
			},
		}

		organizedComments := organizeCommentsByCategory(inputComments)
		So(mergeComments(organizedComments, "test.file"), ShouldResemble, inputComments)
	})
}
