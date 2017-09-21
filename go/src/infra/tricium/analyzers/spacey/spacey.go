// Copyright 2017 The Chromium Authors. All rights reserved.
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
	"unicode"

	"infra/tricium/api/v1"
)

const (
	category = "Spacey"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument")
	}

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %+v", input)

	// Create RESULTS data.
	output := &tricium.Data_Results{}
	for _, p := range input.Paths {
		file, err := os.Open(filepath.Join(*inputDir, p))
		if err != nil {
			log.Fatalf("Failed to open file: %v, path: %s", err, p)
		}
		defer func() {
			if err := file.Close(); err != nil {
				log.Fatalf("Failed to close file: %v, path: %s", err, p)
			}
		}()
		scanner := bufio.NewScanner(file)
		pos := 1
		for scanner.Scan() {
			line := scanner.Text()
			if c := checkSpaceMix(p, line, pos); c != nil {
				output.Comments = append(output.Comments, c)
			}
			if c := checkTrailingSpace(p, line, pos); c != nil {
				output.Comments = append(output.Comments, c)
			}
			pos++
		}
		if err := scanner.Err(); err != nil {
			log.Fatalf("Failed to read file: %v, path: %s", err, p)
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %v\n", path, output)
}

// checkSpaceMix looks for a mix of white space characters in the start of the provided line.
func checkSpaceMix(path, line string, pos int) *tricium.Data_Comment {
	// Three space detectors, each to be set to one if there was an occurence.
	ws := 0
	tab := 0
	other := 0
	// Potential comment position.
	start := 0
	end := 0
	for ; end < len(line) && unicode.IsSpace(rune(line[end])); end++ {
		switch line[end] {
		case ' ':
			ws = 1
		case '\t':
			tab = 1
		default:
			other = 1
		}
	}
	// Add a comment if there was a whites space section and more than one kind of space.
	if start != end && (ws+tab+other > 1) {
		return &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "SpaceMix"),
			Message:   "Found mix of white space characters",
			Path:      path,
			StartLine: int32(pos),
			EndLine:   int32(pos),
			StartChar: int32(start),
			EndChar:   int32(end - 1),
		}
	}
	return nil
}

// checkTrailingSpace looks for white spaces at the end of the provided line.
func checkTrailingSpace(path, line string, pos int) *tricium.Data_Comment {
	if len(line) == 0 {
		return nil
	}
	end := len(line) - 1
	start := end
	for ; start >= 0 && unicode.IsSpace(rune(line[start])); start-- {
	}
	if start != end {
		return &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "TrailingSpace"),
			Message:   "Found trailing space",
			Path:      path,
			StartLine: int32(pos),
			EndLine:   int32(pos),
			StartChar: int32(start + 1),
			EndChar:   int32(end),
		}
	}
	return nil
}
