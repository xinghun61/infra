// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	tricium "infra/tricium/api/v1"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	// Filter the files to only include *.mojom.
	output := &tricium.Data_Results{}
	files, err := tricium.FilterFiles(input.Files, "*.mojom")
	if err != nil {
		log.Fatalf("Failed to filter files: %v", err)
	}

	// Create RESULTS data.
	for _, file := range files {
		p := file.Path
		file, err := os.Open(filepath.Join(*inputDir, p))
		if err != nil {
			log.Fatalf("Failed to open file %q: %v", p, err)
		}
		comments := analyzeFile(bufio.NewScanner(file), p)
		output.Comments = append(output.Comments, comments...)
		if err := file.Close(); err != nil {
			log.Fatalf("Failed to close file %q: %v", p, err)
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

var interfacePattern = regexp.MustCompile(`interface\s+(\w+)\s*{`)

func analyzeFile(scanner *bufio.Scanner, path string) (results []*tricium.Data_Comment) {
	// Tracks if the previous and current line are comments.
	prevLineIsComment := false
	lineIsComment := false

	// Tracks whether the parser is in a meaningful context for analysis.
	inInterface := false
	inMethod := false

	// Starts at 0 so that the counter can be incremented at the top of the
	// loop, for early continues.
	lineNumber := 0

	for scanner.Scan() {
		lineNumber++
		line := scanner.Text()

		// Remove leading indent whitespace.
		line = strings.TrimLeft(line, " \t")

		// Rotate the comment detector flags.
		prevLineIsComment = lineIsComment
		commentIndex := strings.Index(line, "//")
		lineIsComment = commentIndex == 0
		if commentIndex != -1 {
			// Remove any commented content, so that it is not analyzed.
			line = line[:commentIndex]
		}

		if line == "" {
			continue
		}

		closeBraceIndex := strings.Index(line, "}")
		if closeBraceIndex != -1 {
			// This cheap-o parser does not parse all scopes (e.g. structs), so just
			// assume the nesting is valid.
			inInterface = false
		}

		// Check if this line is starting an interface.
		matches := interfacePattern.FindStringSubmatch(line)
		if matches != nil {
			interfaceName := matches[1]
			if inInterface {
				log.Printf("Unexpected nested interface at line %s line %d", path, lineNumber)
				break
			}
			inInterface = true

			if !prevLineIsComment {
				comment := makeComment(path, lineNumber, "interface",
					fmt.Sprintf("Interface %q should have a top-level comment that at minimum describes the caller and callee and the high-level purpose.", interfaceName))
				results = append(results, comment)
			}
		} else if inInterface {
			if !prevLineIsComment && !inMethod {
				comment := makeComment(path, lineNumber, "method",
					"This method should have a comment describing its behavior, inputs, and outputs.")
				results = append(results, comment)
			}

			// The only valid constructs within an interface are comments and
			// methods, so if the line does not end in a semicolon to indicate
			// end-of-method, then the method will continue to the next line.
			endMethodIndex := strings.Index(line, ";")
			inMethod = endMethodIndex == -1
		}
	}

	return
}

func makeComment(path string, line int, subcategory, message string) *tricium.Data_Comment {
	const url = "https://chromium.googlesource.com/chromium/src/+/master/docs/security/mojo.md#Documentation"
	return &tricium.Data_Comment{
		Category:  fmt.Sprintf("MojomCommentator/%s", subcategory),
		Message:   fmt.Sprintf("%s\n\nSee %s for details.", message, url),
		Url:       url,
		Path:      path,
		StartLine: int32(line),
	}
}
