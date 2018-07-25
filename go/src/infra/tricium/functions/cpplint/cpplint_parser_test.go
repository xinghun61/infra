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

	Convey("scanPylintOutput", t, func() {

		Convey("Parsing empty buffer gives no warnings", func() {
			buf := strings.NewReader("")
			s := bufio.NewScanner(buf)
			So(s, ShouldNotBeNil)

			results := &tricium.Data_Results{}
			scanCpplintOutput(s, results, nil)
			So(results.Comments, ShouldBeEmpty)
		})

		Convey("Parsing normal pylint output generates the appropriate comments", func() {
			output := "test.cpp:2:  Line ends in whitespace.  Consider deleting these extra spaces.  [whitespace/end_of_line] [4]\n" +
				"test.cpp:0:  No copyright message found.  You should have a line: \"Copyright [year] <Copyright Owner>\"  [legal/copyright] [5]\n" +
				"test.cpp:141:  If an else has a brace on one side, it should have it on both  [readability/braces] [5]\n" +
				"test.cpp:42:  Add #include <vector> for vector<>  [build/include_what_you_use] [4]\n" +
				"test.cpp:125:  An else should appear on the same line as the preceding }  [whitespace/newline] [4]\n" +
				"test.cpp:129:  Tab found; better to use spaces  [whitespace/tab] [1]\n"

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Category:  "Cpplint/whitespace/end_of_line",
						Message:   "Line ends in whitespace.  Consider deleting these extra spaces. | Confidence (1-5): 4",
						Path:      "test.cpp",
						StartLine: 2,
					},
					{
						Category:  "Cpplint/legal/copyright",
						Message:   "No copyright message found.  You should have a line: \"Copyright [year] <Copyright Owner>\" | Confidence (1-5): 5",
						Path:      "test.cpp",
						StartLine: 0,
					},
					{
						Category:  "Cpplint/readability/braces",
						Message:   "If an else has a brace on one side, it should have it on both | Confidence (1-5): 5",
						Path:      "test.cpp",
						StartLine: 141,
					},
					{
						Category:  "Cpplint/build/include_what_you_use",
						Message:   "Add #include <vector> for vector<> | Confidence (1-5): 4",
						Path:      "test.cpp",
						StartLine: 42,
					},
					{
						Category:  "Cpplint/whitespace/newline",
						Message:   "An else should appear on the same line as the preceding } | Confidence (1-5): 4",
						Path:      "test.cpp",
						StartLine: 125,
					},
					{
						Category:  "Cpplint/whitespace/tab",
						Message:   "Tab found; better to use spaces | Confidence (1-5): 1",
						Path:      "test.cpp",
						StartLine: 129,
					},
				},
			}

			results := &tricium.Data_Results{}
			scanCpplintOutput(bufio.NewScanner(strings.NewReader(output)), results, nil)
			So(results, ShouldResemble, expected)
		})
	})

	Convey("parsePylintLine", t, func() {

		Convey("Parsing valid line gives a comment", func() {
			line := "test.cpp:148:  Line ends in whitespace.  Consider deleting these extra spaces.  [whitespace/end_of_line] [4]"
			So(parseCpplintLine(line), ShouldResemble, &tricium.Data_Comment{
				Category:  "Cpplint/whitespace/end_of_line",
				Message:   "Line ends in whitespace.  Consider deleting these extra spaces. | Confidence (1-5): 4",
				Path:      "test.cpp",
				StartLine: 148,
			})
		})

		Convey("Parsing some other line gives nil", func() {
			So(parseCpplintLine("Total errors found: 24"), ShouldBeNil)
		})
	})
}
