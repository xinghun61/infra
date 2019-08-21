// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the commitcheck analyzer.
package main

import (
	"flag"
	"log"
	"regexp"
	"strings"

	"infra/tricium/api/v1"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument")
	}

	// Read Tricium input GIT_FILE_DETAILS data.
	input := &tricium.Data_GitFileDetails{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read GIT_FILE_DETAILS data: %v", err)
	}

	results := &tricium.Data_Results{}

	checkForTest(input.CommitMessage, results)
	checkForBug(input.CommitMessage, results)

	// Write Tricium RESULTS data.
	_, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
}

func checkForTest(commitMessage string, results *tricium.Data_Results) {
	exp := regexp.MustCompile(`[[:blank:]]*TEST=[[:blank:]]*\S+`)
	if !exp.MatchString(commitMessage) {
		var comment = tricium.Data_Comment{
			Message:   "No TEST= or empty TEST= found in commit message.",
			Category:  "CommitCheck/NoTestFound",
			StartLine: 0,
		}
		results.Comments = append(results.Comments, &comment)
	}
}

func checkForBug(commitMessage string, results *tricium.Data_Results) {
	exp := regexp.MustCompile(`[[:blank:]]*BUG=(.*)`)

	for lineNum, line := range strings.Split(commitMessage, "\n") {
		if exp.MatchString(line) {
			// Check that the BUG= entry contains a usable link
			bugLink := exp.FindStringSubmatch(line)[1]
			exp = regexp.MustCompile(`(b|chromium):\d+`)
			if !exp.MatchString(bugLink) {
				var comment = tricium.Data_Comment{
					Message:   "No valid bug found. Use format b:123 or chromium:123.",
					Category:  "CommitCheck/InvalidBugDescription",
					StartLine: int32(lineNum + 1),
				}
				results.Comments = append(results.Comments, &comment)
			}
			return
		}
	}

	var comment = tricium.Data_Comment{
		Message:   "No BUG= found in commit message.",
		Category:  "CommitCheck/NoBugFound",
		StartLine: 0,
	}
	results.Comments = append(results.Comments, &comment)
}
