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
	"strings"
)

const (
	category                = "Spacey"
	individualCommentsLimit = 3
	tabLength               = 8
)

var (
	mixedWhitespaceBlacklist = []string{".mk", "makefile", "Makefile", ".patch"}
	trailingSpaceBlacklist   = []string{".patch", ".pdf"}
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
	for _, file := range input.Files {
		if file.IsBinary {
			log.Printf("Not performing Spacey checks on binary file: %s", file.Path)
			return
		}
		p := file.Path
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
		var comments []*tricium.Data_Comment
		for scanner.Scan() {
			line := scanner.Text()
			if c := checkSpaceMix(p, line, pos); c != nil {
				comments = append(comments, c)
			}
			if c := checkTrailingSpace(p, line, pos); c != nil {
				comments = append(comments, c)
			}
			pos++
		}
		if err := scanner.Err(); err != nil {
			log.Fatalf("Failed to read file: %v, path: %s", err, p)
		}

		commentFreqs := organizeCommentsByCategory(comments)
		output.Comments = mergeComments(commentFreqs, p)
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %v\n", path, output)
}

// checkSpaceMix looks for a mix of white space characters in the start of the provided line.
//
// TODO(qyearsley): Check for space mix in the middle of the line too.
func checkSpaceMix(path, line string, pos int) *tricium.Data_Comment {
	if isInBlacklist(path, mixedWhitespaceBlacklist) {
		log.Printf("Not emitting comments for file: %s", path)
		return nil
	}

	// Space detector flags, each to be set to 1 if there was an occurrence.
	var spaceFlag, tabFlag, otherFlag int

	// Count number of occurrences for different types of spaces.
	var numSpaces, numTabs int

	// Potential comment position.
	start := 0
	end := 0
	for ; end < len(line) && unicode.IsSpace(rune(line[end])); end++ {
		switch line[end] {
		case ' ':
			spaceFlag = 1
			numSpaces++
		case '\t':
			tabFlag = 1
			numTabs++
		default:
			otherFlag = 1
		}
	}

	// Add a comment if there was a whitespace section and more than one kind of space.
	if start != end && (spaceFlag+tabFlag+otherFlag > 1) {
		comment := &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "SpaceMix"),
			Message:   "Found mix of white space characters",
			Path:      path,
			StartLine: int32(pos),
			EndLine:   int32(pos),
			StartChar: int32(start),
			EndChar:   int32(end - 1),
		}

		// Whitespace characters that are neither tabs nor spaces are deleted,
		// indentation starts with either 8 spaces or one tab.
		indentationSpaces := numTabs*tabLength + numSpaces

		comment.Suggestions = []*tricium.Data_Suggestion{
			{
				Replacements: []*tricium.Data_Replacement{
					{
						// Suggest using all spaces.
						Replacement: insertWhitespace(line[end:], indentationSpaces, false),
						Path:        path,
						StartLine:   int32(pos),
						EndLine:     int32(pos),
						StartChar:   0,
						EndChar:     int32(len(line)),
					},
				},
				Description: "Replace all whitespace at the beginning of the line with spaces",
			},
			{
				Replacements: []*tricium.Data_Replacement{
					{
						// Suggest using all tabs (only multiples of 8, other spaces get ignored).
						Replacement: insertWhitespace(line[end:], indentationSpaces/tabLength, true),
						Path:        path,
						StartLine:   int32(pos),
						EndLine:     int32(pos),
						StartChar:   0,
						EndChar:     int32(len(line)),
					},
				},
				Description: "Replace all whitespace at the beginning of the line with tabs",
			},
		}

		return comment
	}

	return nil
}

// checkTrailingSpace looks for white spaces at the end of the provided line.
func checkTrailingSpace(path, line string, pos int) *tricium.Data_Comment {
	if isInBlacklist(path, trailingSpaceBlacklist) {
		log.Printf("Not emitting comments for file: %s", path)
		return nil
	}

	if len(line) == 0 {
		return nil
	}

	end := len(line) - 1
	start := end
	for ; start >= 0 && unicode.IsSpace(rune(line[start])); start-- {
	}

	if start != end {
		comment := &tricium.Data_Comment{
			Category:  fmt.Sprintf("%s/%s", category, "TrailingSpace"),
			Message:   "Found trailing space",
			Path:      path,
			StartLine: int32(pos),
			EndLine:   int32(pos),
			StartChar: int32(start + 1),
			EndChar:   int32(end),
		}

		comment.Suggestions = []*tricium.Data_Suggestion{
			{
				Replacements: []*tricium.Data_Replacement{
					{
						Replacement: line[0 : start+1],
						Path:        path,
						StartLine:   int32(pos),
						EndLine:     int32(pos),
						StartChar:   0,
						EndChar:     int32(len(line) - 1),
					},
				},
				Description: "Get rid of trailing space",
			},
		}

		return comment
	}

	return nil
}

// Checks whether a path matches the given blacklist, where the blacklist
// contains either file extensions or complete filenames.
func isInBlacklist(path string, blacklist []string) bool {
	for _, ext := range blacklist {
		if ext == filepath.Ext(path) || ext == filepath.Base(path) {
			return true
		}
	}
	return false
}

// Groups comments of the same categories together into a map of comment category to list of comments.
func organizeCommentsByCategory(comments []*tricium.Data_Comment) map[string][]*tricium.Data_Comment {
	commentFreqs := make(map[string][]*tricium.Data_Comment)

	for _, comment := range comments {
		elem, ok := commentFreqs[comment.Category]
		if ok {
			commentFreqs[comment.Category] = append(elem, comment)
		} else {
			commentFreqs[comment.Category] = []*tricium.Data_Comment{comment}
		}
	}

	return commentFreqs
}

// Merges comments with the same category together if their number of occurrences is lower than individualCommentsLimit.
func mergeComments(commentFreqs map[string][]*tricium.Data_Comment, path string) []*tricium.Data_Comment {
	var comments []*tricium.Data_Comment

	for cat, categoryComments := range commentFreqs {
		if len(categoryComments) < individualCommentsLimit {
			comments = append(comments, categoryComments...)
		} else {
			comments = append(comments, &tricium.Data_Comment{
				Category: cat,
				Message:  fmt.Sprintf("Found %d %s warnings in this file", len(categoryComments), cat),
				Path:     path,
			})
		}
	}

	return comments
}

// Inserts n tabs or spaces to the beginning of a line.
func insertWhitespace(line string, n int, tabs bool) string {
	s := " "
	if tabs {
		s = "\t"
	}
	return strings.Repeat(s, n) + line
}
