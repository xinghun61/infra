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

		Convey("Parsing normal cpplint output generates the appropriate comments", func() {
			output := "test.cc:0:  No copyright message found  [legal/copyright] [5]\n" +
				"test.cc:141:  If an else has a brace on one side, it should have it on both  [readability/braces] [5]\n" +
				"test.cc:42:  Add #include <vector> for vector<>  [build/include_what_you_use] [4]\n"

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Category: "Cpplint/legal/copyright",
						Message: "No copyright message found (confidence 5/5).\n" +
							"To disable, add: // NOLINT(legal/copyright)",
						Path:      "test.cc",
						StartLine: 0,
					},
					{
						Category: "Cpplint/readability/braces",
						Message: "If an else has a brace on one side, " +
							"it should have it on both (confidence 5/5).\n" +
							"To disable, add: // NOLINT(readability/braces)",
						Path:      "test.cc",
						StartLine: 141,
					},
					{
						Category: "Cpplint/build/include_what_you_use",
						Message: "Add #include <vector> for vector<> (confidence 4/5).\n" +
							"To disable, add: // NOLINT(build/include_what_you_use)",
						Path:      "test.cc",
						StartLine: 42,
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
			line := "test.cc:148:  This is the helpful explanation  [readability/foo] [4]"
			So(parseCpplintLine(line), ShouldResemble, &tricium.Data_Comment{
				Category: "Cpplint/readability/foo",
				Message: "This is the helpful explanation (confidence 4/5).\n" +
					"To disable, add: // NOLINT(readability/foo)",
				Path:      "test.cc",
				StartLine: 148,
			})
		})

		Convey("Parsing some other line gives nil", func() {
			So(parseCpplintLine("Total errors found: 24"), ShouldBeNil)
		})
	})
}
