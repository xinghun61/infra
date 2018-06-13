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
			scanPylintOutput(s, results, nil)
			So(results.Comments, ShouldBeEmpty)
		})

		Convey("Parsing normal pylint output generates the appropriate comments", func() {
			output := "test.py:6:0 [convention/empty-docstring] Empty function docstring\n" +
				"test.py:6:15 [warning/unused-argument] Unused argument 'y'\n" +
				"test.py:6:18 [warning/unused-argument] Unused argument 'z'\n" +
				"test.py:12:2 [warning/unnecessary-pass] Unnecessary pass statement\n" +
				"test.py:19:10 [warning/undefined-loop-variable] Using possibly undefined loop variable 'a'\n" +
				"test.py:18:6 [warning/unused-variable] Unused variable 'a'\n" +
				"test.py:26:0 [error/undefined-variable] Undefined variable 'main'\n"

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Path:      "test.py",
						Message:   "Empty function docstring",
						Category:  "Pylint/convention/empty-docstring",
						StartLine: 6,
						StartChar: 0,
					},
					{
						Path:      "test.py",
						Message:   "Unused argument 'y'",
						Category:  "Pylint/warning/unused-argument",
						StartLine: 6,
						StartChar: 15,
					},
					{
						Path:      "test.py",
						Message:   "Unused argument 'z'",
						Category:  "Pylint/warning/unused-argument",
						StartLine: 6,
						StartChar: 18,
					},
					{
						Path:      "test.py",
						Message:   "Unnecessary pass statement",
						Category:  "Pylint/warning/unnecessary-pass",
						StartLine: 12,
						StartChar: 2,
					},
					{
						Path:      "test.py",
						Message:   "Using possibly undefined loop variable 'a'",
						Category:  "Pylint/warning/undefined-loop-variable",
						StartLine: 19,
						StartChar: 10,
					},
					{
						Path:      "test.py",
						Message:   "Unused variable 'a'",
						Category:  "Pylint/warning/unused-variable",
						StartLine: 18,
						StartChar: 6,
					},
					{
						Path:      "test.py",
						Message:   "Undefined variable 'main'",
						Category:  "Pylint/error/undefined-variable",
						StartLine: 26,
						StartChar: 0,
					},
				},
			}

			results := &tricium.Data_Results{}
			scanPylintOutput(bufio.NewScanner(strings.NewReader(output)), results, nil)
			So(results, ShouldResemble, expected)
		})
	})

	Convey("parsePylintLine", t, func() {

		Convey("Parsing valid line gives a comment", func() {
			line := "src/foo.py:45:12 [warning/unused-argument] Unused argument 'z'"
			So(parsePylintLine(line), ShouldResemble, &tricium.Data_Comment{
				Category:  "Pylint/warning/unused-argument",
				Message:   "Unused argument 'z'",
				Path:      "src/foo.py",
				StartLine: 45,
				StartChar: 12,
			})
		})

		Convey("Parsing some other line gives nil", func() {
			So(parsePylintLine("*********** Module name"), ShouldBeNil)
		})
	})
}
