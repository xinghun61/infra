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

func TestSpellCheckerAnalyzeFiles(t *testing.T) {
	// These tests depend on both dictionary.txt and comment_formats.json.
	Convey("Analyzing simple file with one misspelling generates one comment", t, func() {
		fileContent := "/* coment */"
		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"coment" is a possible misspelling of "comment".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 3,
					EndChar:   9,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "comment",
									StartLine:   1,
									EndLine:     1,
									StartChar:   3,
									EndChar:     10,
								},
							},
						},
					},
				},
			},
		}
		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})

	Convey("Analyzing a .c file with several comments.", t, func() {
		fileContent := "// The misspelling iminent is mapped to three possible fixes.\n" +
			"This is not in a comment so aberation shouldn't be flagged.\n" +
			"//The word wanna has a reason to be disabled, so isn't flagged\n" +
			"/*Here are\ncombinatins of\nlines.\nAnd GAE is ignored.*/\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"iminent" is a possible misspelling of "eminent", "imminent", or "immanent".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 19,
					EndChar:   26,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "eminent",
									StartLine:   1,
									EndLine:     1,
									StartChar:   19,
									EndChar:     26,
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
									StartChar:   19,
									EndChar:     27,
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
									StartChar:   19,
									EndChar:     27,
								},
							},
						},
					},
				},
				{
					Path:      "test.c",
					Message:   `"combinatins" is a possible misspelling of "combinations".`,
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
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})

	Convey("One line with both types of comment patterns", t, func() {
		fileContent := "/*beggining//code*//*beccause*/\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"beggining" is a possible misspelling of "beginning".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 2,
					EndChar:   11,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "beginning",
									StartLine:   1,
									EndLine:     1,
									StartChar:   2,
									EndChar:     11,
								},
							},
						},
					},
				},
				{
					Path:      "test.c",
					Message:   `"beccause" is a possible misspelling of "because".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 21,
					EndChar:   29,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "because",
									StartLine:   1,
									EndLine:     1,
									StartChar:   21,
									EndChar:     28,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})

	Convey("Block comment across multiple lines", t, func() {
		fileContent := "/*An\nabandonded\ncalcualtion.*/\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"abandonded" is a possible misspelling of "abandoned".`,
					Category:  "SpellChecker",
					StartLine: 2,
					EndLine:   2,
					StartChar: 0,
					EndChar:   10,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "abandoned",
									StartLine:   2,
									EndLine:     2,
									StartChar:   0,
									EndChar:     9,
								},
							},
						},
					},
				},
				{
					Path:      "test.c",
					Message:   `"calcualtion" is a possible misspelling of "calculation".`,
					Category:  "SpellChecker",
					StartLine: 3,
					EndLine:   3,
					StartChar: 0,
					EndChar:   11,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "calculation",
									StartLine:   3,
									EndLine:     3,
									StartChar:   0,
									EndChar:     11,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})

	Convey("One line comment with // separating misspelled words", t, func() {
		fileContent := "//Doccument//divertion, docrines\ndoas\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"Doccument" is a possible misspelling of "Document".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 2,
					EndChar:   11,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "Document",
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
					Message:   `"divertion" is a possible misspelling of "diversion".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 13,
					EndChar:   22,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "diversion",
									StartLine:   1,
									EndLine:     1,
									StartChar:   13,
									EndChar:     22,
								},
							},
						},
					},
				},
				{
					Path:      "test.c",
					Message:   `"docrines" is a possible misspelling of "doctrines".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 24,
					EndChar:   32,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "doctrines",
									StartLine:   1,
									EndLine:     1,
									StartChar:   24,
									EndChar:     33,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})

	Convey("All words in a text file are analyzed", t, func() {
		fileContent := "Familes\nfaund\nnormal\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.txt",
					Message:   `"Familes" is a possible misspelling of "Families".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 0,
					EndChar:   7,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.txt",
									Replacement: "Families",
									StartLine:   1,
									EndLine:     1,
									StartChar:   0,
									EndChar:     8,
								},
							},
						},
					},
				},
				{
					Path:      "test.txt",
					Message:   `"faund" is a possible misspelling of "found".`,
					Category:  "SpellChecker",
					StartLine: 2,
					EndLine:   2,
					StartChar: 0,
					EndChar:   5,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.txt",
									Replacement: "found",
									StartLine:   2,
									EndLine:     2,
									StartChar:   0,
									EndChar:     5,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.txt", results)
		So(results, ShouldResemble, expected)
	})

	Convey("Analyzing file with unknown extension generates no comments", t, func() {
		fileContent := "familes\n"
		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.asdf", results)
		So(results.Comments, ShouldBeEmpty)
	})

	Convey("Usernames are not flagged as misspellings.", t, func() {
		fileContent := "TODO(faund): Contact govement@chromium.org/coment"
		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.txt", results)
		So(results.Comments, ShouldBeEmpty)
	})

	Convey("Analyzing HTML file generates appropriate comments", t, func() {
		fileContent := "<!DOCTYPE html>\n<html>\n<head>\n<!--coment-->\n</head>\n</html>\n"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.html",
					Message:   `"coment" is a possible misspelling of "comment".`,
					Category:  "SpellChecker",
					StartLine: 4,
					EndLine:   4,
					StartChar: 4,
					EndChar:   10,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.html",
									Replacement: "comment",
									StartLine:   4,
									EndLine:     4,
									StartChar:   4,
									EndChar:     11,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.html", results)
		So(results, ShouldResemble, expected)
	})

	Convey("Same misspelling multiple times in one line", t, func() {
		fileContent := "//twpo twpo"

		expected := &tricium.Data_Results{
			Comments: []*tricium.Data_Comment{
				{
					Path:      "test.c",
					Message:   `"twpo" is a possible misspelling of "two".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 2,
					EndChar:   6,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "two",
									StartLine:   1,
									EndLine:     1,
									StartChar:   2,
									EndChar:     5,
								},
							},
						},
					},
				},
				{
					Path:      "test.c",
					Message:   `"twpo" is a possible misspelling of "two".`,
					Category:  "SpellChecker",
					StartLine: 1,
					EndLine:   1,
					StartChar: 7,
					EndChar:   11,
					Suggestions: []*tricium.Data_Suggestion{
						{
							Description: "Misspelling fix suggestion",
							Replacements: []*tricium.Data_Replacement{
								{
									Path:        "test.c",
									Replacement: "two",
									StartLine:   1,
									EndLine:     1,
									StartChar:   7,
									EndChar:     10,
								},
							},
						},
					},
				},
			},
		}

		results := &tricium.Data_Results{}
		analyzeFile(bufio.NewScanner(strings.NewReader(fileContent)), "test.c", results)
		So(results, ShouldResemble, expected)
	})
}

func TestGettingCommentFormat(t *testing.T) {
	// This test depends on reading the comment-format file in this
	Convey("The appropriate comment formats are determined from the file extensions", t, func() {
		So(getLangCommentPattern(".py"), ShouldResemble, &commentFormat{
			LineStart:  "#",
			BlockStart: `"""`,
			BlockEnd:   `"""`,
		})

		So(getLangCommentPattern(".c"), ShouldResemble, &commentFormat{
			LineStart:  "//",
			BlockStart: `/*`,
			BlockEnd:   `*/`,
		})

		So(getLangCommentPattern(".html"), ShouldResemble, &commentFormat{
			BlockStart: `<!--`,
			BlockEnd:   `-->`,
		})
	})
}

func TestCommentCaseMatching(t *testing.T) {
	Convey("matchCase converts to upper-case if target appears to be upper-case", t, func() {
		So(matchCase("myword", "TARGET"), ShouldEqual, "MYWORD")
		So(matchCase("myword", "A"), ShouldEqual, "MYWORD")
	})

	Convey("matchCase converts to title-case if target appears to be title case", t, func() {
		So(matchCase("myword", "Myword"), ShouldEqual, "Myword")
		So(matchCase("myword", "TarGet"), ShouldEqual, "Myword")
	})

	Convey("matchCase doesn't convert case if the target has irregular case", t, func() {
		So(matchCase("myword", "tArGeT"), ShouldEqual, "myword")
	})
}
