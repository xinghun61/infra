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

func TestPylintParsingFunctions(t *testing.T) {

	Convey("scanCodespellOutput", t, func() {

		Convey("Looking for a word in a line returns the appropriate range of characters", func() {
			start, end := findWordInLine("test", "this is a test of a function")
			So(start, ShouldEqual, 10)
			So(end, ShouldEqual, 14)
		})

		Convey("Parsing empty buffer gives no warnings", func() {
			s := bufio.NewScanner(strings.NewReader(""))
			So(s, ShouldNotBeNil)

			results := &tricium.Data_Results{}
			scanCodespellOutput(s, bufio.NewScanner(strings.NewReader("file content")), results, nil)
			So(results.Comments, ShouldBeEmpty)
		})

		Convey("Parsing normal codespell output generates the appropriate comments", func() {
			output := "test.txt:1: aberation  ==> aberration\n" +
				"test.txt:2: iminent  ==> eminent, imminent, immanent,\n" +
				"test.txt:3: wanna  ==> want to  | disabled because one might want to allow informal pronunciation\n" +
				"test.txt:5: wanna  ==> want to, wants to, test suggestion | this is a random reason\n" +
				"test.txt:5: combinatins  ==> combinations\n"

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Path:      "test.txt",
						Message:   `"aberation" is a possible misspelling of: aberration`,
						Category:  "SpellChecker",
						StartLine: 1,
						EndLine:   1,
						StartChar: 0,
						EndChar:   9,
					},
					{
						Path:      "test.txt",
						Message:   `"iminent" is a possible misspelling of: eminent, imminent, immanent`,
						Category:  "SpellChecker",
						StartLine: 2,
						EndLine:   2,
						StartChar: 0,
						EndChar:   7,
					},
					{
						Path:      "test.txt",
						Message:   `"wanna" is a possible misspelling of: want to`,
						Category:  "SpellChecker",
						StartLine: 3,
						EndLine:   3,
						StartChar: 0,
						EndChar:   5,
					},
					{
						Path:      "test.txt",
						Message:   `"wanna" is a possible misspelling of: want to, wants to, test suggestion`,
						Category:  "SpellChecker",
						StartLine: 5,
						EndLine:   5,
						StartChar: 0,
						EndChar:   5,
					},
					{
						Path:      "test.txt",
						Message:   `"combinatins" is a possible misspelling of: combinations`,
						Category:  "SpellChecker",
						StartLine: 5,
						EndLine:   5,
						StartChar: 16,
						EndChar:   27,
					},
				},
			}

			results := &tricium.Data_Results{}
			scanCodespellOutput(bufio.NewScanner(strings.NewReader(output)),
				bufio.NewScanner(strings.NewReader("aberation\niminent\nwanna\nnormal line\nwanna test some combinatins\n")),
				results, nil)
			So(results, ShouldResemble, expected)
		})
	})
}
