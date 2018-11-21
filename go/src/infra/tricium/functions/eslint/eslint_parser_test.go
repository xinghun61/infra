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

func TestEslintParsingFunctions(t *testing.T) {

	Convey("scanEslintOutput", t, func() {

		Convey("Parsing empty file gives no warnings", func() {
			buf := strings.NewReader(`[{"filePath":"test.js", "messages":[]}]`)
			s := bufio.NewScanner(buf)
			So(s, ShouldNotBeNil)

			results := &tricium.Data_Results{}
			scanEslintOutput(s, results, nil)
			So(results.Comments, ShouldBeEmpty)
		})

		Convey("Parsing normal eslint output generates the appropriate comments", func() {
			output := `[{"filePath":"/var/lib/test.js",` +
				`"messages":[{"ruleId":"no-unused-vars","severity":2,"message":"'addOne' is defined but never used.",` +
				`"line":1,"column":10,"nodeType":"Identifier","endLine":1,"endColumn":16}],` +
				`"errorCount":1,"warningCount":0,"fixableErrorCount":0,"fixableWarningCount":0},` +
				`{"filePath":"/var/lib/test2.js",` +
				`"messages":[{"ruleId":"camelcase","severity":2,"message":"Identifier 'rabbit_hole' is not in camelcase.",` +
				`"line":2,"column":1,"nodeType":"Identifier","endLine":2,"endColumn":12}],` +
				`"errorCount":1,"warningCount":0,"fixableErrorCount":0,"fixableWarningCount":0}` +
				`]`

			expected := &tricium.Data_Results{
				Comments: []*tricium.Data_Comment{
					{
						Path:      "/var/lib/test.js",
						Category:  "ESLint/error/no-unused-vars",
						Message:   "'addOne' is defined but never used.\nTo disable, add: // eslint-disable-line no-unused-vars",
						StartLine: 1,
						EndLine:   1,
						StartChar: 10,
						EndChar:   16,
					},
					{
						Path:      "/var/lib/test2.js",
						Category:  "ESLint/error/camelcase",
						Message:   "Identifier 'rabbit_hole' is not in camelcase.\nTo disable, add: // eslint-disable-line camelcase",
						StartLine: 2,
						StartChar: 1,
						EndLine:   2,
						EndChar:   12,
					},
				},
			}

			results := &tricium.Data_Results{}
			scanEslintOutput(bufio.NewScanner(strings.NewReader(output)), results, nil)
			So(results, ShouldResemble, expected)
		})
	})
}
