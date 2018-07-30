// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
)

func TestSpellChecker(t *testing.T) {
	Convey("analyzeFiles", t, func() {
		Convey("Looking for a word in a line returns the appropriate range of characters", func() {
			start, end := findWordInLine("test", "this is a test of a function")
			So(start, ShouldEqual, 10)
			So(end, ShouldEqual, 14)
		})

		Convey("The appropriate comment formats are determined from the file extensions", func() {
			pythonFormat := getLangCommentPattern(".py")
			So(pythonFormat, ShouldResemble, &commentFormat{
				singleLine:     "#",
				multilineStart: `"""`,
				multilineEnd:   `"""`,
			})

			cFormat := getLangCommentPattern(".c")
			So(cFormat, ShouldResemble, &commentFormat{
				singleLine:     "//",
				multilineStart: `/*`,
				multilineEnd:   `*/`,
			})

			htmlFormat := getLangCommentPattern(".html")
			So(htmlFormat, ShouldResemble, &commentFormat{
				multilineStart: `<!--`,
				multilineEnd:   `-->`,
			})
		})

		Convey("Analyzing normal C file generates the appropriate comments", func() {
			fileContent := "//iminent\n" +
				"not a comment so aberation shouldn't be flagged\n" +
				"//wanna has a reason to be disabled\n" +
				"/*a\ncombinatins of\nlines\n" +
				"ignore GAE*/\n"

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Path:      "test.c",
						Message:   `"iminent" is a possible misspelling of: eminent, imminent, immanent`,
						Category:  "SpellChecker",
						StartLine: 1,
						EndLine:   1,
						StartChar: 2,
						EndChar:   9,
						Suggestions: []*tricium.Data_Suggestion{
							{
								Description: "Misspelling fix suggestion",
								Replacements: []*tricium.Data_Replacement{
									{
										Path:        "test.c",
										Replacement: "eminent",
										StartLine:   1,
										EndLine:     1,
										StartChar:   2,
										EndChar:     9,
									},
								},
							},
							{
								Description: "Misspelling fix suggestion",
								Replacements: []*tricium.Data_Replacement{
									{
										Path:        "test.c",
										Replacement: "imminent",
										StartLine:   1,
										EndLine:     1,
										StartChar:   2,
										EndChar:     10,
									},
								},
							},
							{
								Description: "Misspelling fix suggestion",
								Replacements: []*tricium.Data_Replacement{
									{
										Path:        "test.c",
										Replacement: "immanent",
										StartLine:   1,
										EndLine:     1,
										StartChar:   2,
										EndChar:     10,
									},
								},
							},
						},
					},
					{
						Path:      "test.c",
						Message:   `"combinatins" is a possible misspelling of: combinations`,
						Category:  "SpellChecker",
						StartLine: 5,
						EndLine:   5,
						StartChar: 0,
						EndChar:   11,
						Suggestions: []*tricium.Data_Suggestion{
							{
								Description: "Misspelling fix suggestion",
								Replacements: []*tricium.Data_Replacement{
									{
										Path:        "test.c",
										Replacement: "combinations",
										StartLine:   5,
										EndLine:     5,
										StartChar:   0,
										EndChar:     12,
									},
								},
							},
						},
					},
				},
			}

			results := &tricium.Data_Results{}
			analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", buildDict("dictionary.txt"), results)
			So(results, ShouldResemble, expected)
		})
	})
}
