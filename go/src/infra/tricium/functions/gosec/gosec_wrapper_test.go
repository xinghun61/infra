// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"infra/tricium/api/v1"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGosecWrapper(t *testing.T) {

	Convey("Test min function", t, func() {
		So(min(3, 4), ShouldResemble, 3)
		So(min(-1, 4), ShouldResemble, -1)
		So(min(-3, -4), ShouldResemble, -4)
		So(min(0, 0), ShouldResemble, 0)
	})

	Convey("hashIssue function is implementation of sha256", t, func() {
		issue := Issue{
			Severity:   "HIGH",
			Confidence: "LOW",
			RuleID:     "G101",
			Details:    "test",
			File:       "./test/example.py",
			Code:       "",
			Line:       "10",
		}
		other := issue
		expected := [32]uint8{
			112, 173, 182, 160, 71, 177, 218, 240,
			58, 93, 77, 99, 62, 79, 78, 204, 235,
			197, 93, 185, 153, 150, 175, 29, 50,
			100, 216, 6, 214, 98, 109, 251}

		So(hashIssue(&issue), ShouldResemble, expected)
		// Assert x = y -> f(x) = f(y)
		So(hashIssue(&issue), ShouldResemble, hashIssue(&other))
	})

	Convey("Test postProcess function", t, func() {
		*inputDir = ""
		f1, _ := filepath.Abs("example.go")
		f2, _ := filepath.Abs("example2.go")
		f3, _ := filepath.Abs("example3.go")
		f4, _ := filepath.Abs("example4.go")

		issue1 := Issue{
			Severity:   "HIGH",
			Confidence: "LOW",
			RuleID:     "G101",
			Details:    "",
			File:       f1,
			Code:       "",
			Line:       "1",
		}
		issue1.Hash = hashIssue(&issue1)

		issue2 := Issue{
			Severity:   "HIGH",
			Confidence: "MEDIUM",
			RuleID:     "G101",
			Details:    "",
			File:       f2,
			Code:       "",
			Line:       "1",
		}
		issue2.Hash = hashIssue(&issue2)

		issue3 := Issue{
			Severity:   "HIGH",
			Confidence: "LOW",
			RuleID:     "G101",
			Details:    "",
			File:       f3,
			Code:       "",
			Line:       "2",
		}
		issue3.Hash = hashIssue(&issue3)

		issue4 := Issue{
			Severity:   "HIGH",
			Confidence: "LOW",
			RuleID:     "G103",
			Details:    "",
			File:       f4,
			Code:       "",
			Line:       "1",
		}
		issue4.Hash = hashIssue(&issue4)

		results := []GosecResult{
			{
				Issues: []Issue{
					issue1,
					issue2,
					issue3,
					issue4,
				},
			},
			{
				Issues: []Issue{
					issue1,
					issue2,
					issue3,
					issue4,
				},
			},
			{
				Issues: []Issue{
					issue1,
					issue2,
					issue3,
					issue4,
				},
			},
			{
				Issues: []Issue{
					issue1,
					issue2,
					issue3,
					issue4,
				},
			},
		}

		input := []*tricium.Data_File{
			{
				Path: "example.go",
			},
			{
				Path: "example2.go",
			},
		}

		So(len(postProcess(results, input, false)), ShouldResemble, 2)
	})

}
