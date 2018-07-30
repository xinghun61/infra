// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"

	"infra/tricium/api/v1"
)

type commentFormat struct {
	singleLine     string
	multilineStart string
	multilineEnd   string
}

const (
	commentsJSONPath = "comment_formats.json"
	dictPath         = "dictionary.txt"
)

// TODO(diegomtzg): Do we want to keep a whitelist of words or just remove them from the dictionary?
var whitelistWords = []string{"gae"}
var textFileExts = []string{".txt", ".md"}

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
	log.Printf("Read FILES data: %#v", input)

	dict := buildDict(dictPath)
	results := &tricium.Data_Results{}

	for _, file := range input.Files {
		if !file.IsBinary {
			p := filepath.Join(*inputDir, file.Path)

			f := openFileOrDie(p)
			defer closeFileOrDie(f)

			analyzeFile(bufio.NewScanner(f), p, dict, results)
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, results)
}

func analyzeFile(scanner *bufio.Scanner, filePath string, dict map[string][]string,
	results *tricium.Data_Results) {
	lineno := 1
	inTxtFile, inBlockComment, lastWordInBlock := false, false, false
	fileExt := filepath.Ext(filePath)

	// Skip files with no extension since we don't know what type of file they are.
	if fileExt == "" {
		return
	}

	// The analyzer should check every word if the file is a text document.
	if inSlice(fileExt, textFileExts) {
		inTxtFile = true
	}

	commentPatterns := getLangCommentPattern(fileExt)

	for scanner.Scan() {
		inSingleComment := false

		line := scanner.Text()
		words := strings.Fields(line)

		// TODO(diegomtzg): Also check string literals, not just comments.
		for _, word := range words {
			// Some languages don't have single line comments (e.g. HTML), so ignore this check.
			if len(commentPatterns.singleLine) > 0 && strings.Contains(word, commentPatterns.singleLine) {
				inSingleComment = true
				word = strings.SplitN(word, commentPatterns.singleLine, 2)[1]
			} else if strings.Contains(word, commentPatterns.multilineStart) {
				// TODO(diegomtzg): A line could have multiple block comments (currently not supported)
				inBlockComment = true
				word = strings.Split(word, commentPatterns.multilineStart)[1]
			}
			if strings.Contains(word, commentPatterns.multilineEnd) {
				lastWordInBlock = true
				word = strings.Split(word, commentPatterns.multilineEnd)[0]
			}

			if len(word) > 0 && (inTxtFile || inSingleComment || inBlockComment) {
				if fixes, ok := dict[word]; ok {
					if comment := buildMisspellingComment(word, fixes, line, lineno, filePath); comment != nil {
						results.Comments = append(results.Comments, comment)
					}
				}
			}

			if lastWordInBlock {
				inBlockComment = false
				lastWordInBlock = false
			}
		}
		// Line ends, no longer in single-line comment.
		inSingleComment = false
		lineno++
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v, path: %s", err, filePath)
	}
}

// Finds the character range of a word in a given line.
func findWordInLine(word string, line string) (int, int) {
	startChar := strings.Index(line, word)
	if startChar == -1 {
		return 0, 0
	}
	return startChar, startChar + len(word)
}

func buildDict(dictPath string) map[string][]string {
	f := openFileOrDie(dictPath)
	defer closeFileOrDie(f)

	dictMap := make(map[string][]string)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()

		// Misspellings are at data[0] and fixes are at data[1].
		data := strings.Split(line, "->")
		fixes := strings.Split(data[1], ", ")
		dictMap[data[0]] = fixes
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v, path: %s", err, dictPath)
	}

	return dictMap
}

func buildMisspellingComment(misspelling string, fixes []string, line string, lineno int,
	path string) *tricium.Data_Comment {
	// If there is more than one fix and the last character of the last element of fixes
	// doesn't have a comma, the word has a reason to be disabled.
	if len(fixes) > 1 && !strings.HasSuffix(fixes[len(fixes)-1], ",") {
		log.Printf("SKIPPING: %q has a reason to be disabled "+
			"in the CodeSpell dictionary.", misspelling)
		return nil
	}

	// Get rid of trailing comma in last fix.
	fixes[len(fixes)-1] = strings.Replace(fixes[len(fixes)-1], ",", "", -1)
	log.Printf("ADDING %q with fixes: %q\n", misspelling, fixes)
	startChar, endChar := findWordInLine(misspelling, line)

	var suggestions []*tricium.Data_Suggestion
	for _, fix := range fixes {
		suggestions = append(suggestions, &tricium.Data_Suggestion{
			Description: fmt.Sprintf("Misspelling fix suggestion"),
			Replacements: []*tricium.Data_Replacement{
				{
					Path:        path,
					Replacement: fix,
					StartLine:   int32(lineno),
					EndLine:     int32(lineno),
					StartChar:   int32(startChar),
					EndChar:     int32(startChar + len(fix)),
				},
			},
		})
	}

	return &tricium.Data_Comment{
		Path: path,
		Message: fmt.Sprintf("%q is a possible misspelling of: %s", misspelling,
			strings.Join(fixes, ", ")),
		Category:    "SpellChecker",
		StartLine:   int32(lineno),
		EndLine:     int32(lineno),
		StartChar:   int32(startChar),
		EndChar:     int32(endChar),
		Suggestions: suggestions,
	}
}

// Gets the appropriate comment pattern for the programming lanaguage determined by the given
// file extension.
func getLangCommentPattern(fileExt string) *commentFormat {
	commentFmtMap := loadCommentsJSONFile()
	cmtFormatEntry := commentFmtMap[fileExt]
	commentPatterns := &commentFormat{
		singleLine:     cmtFormatEntry["single-line"],
		multilineStart: cmtFormatEntry["multi-line start"],
		multilineEnd:   cmtFormatEntry["multi-line end"],
	}

	return commentPatterns
}

func loadCommentsJSONFile() map[string]map[string]string {
	var commentsMap map[string]map[string]string

	f := openFileOrDie(commentsJSONPath)
	defer closeFileOrDie(f)

	jsonBytes, _ := ioutil.ReadAll(f)
	if err := json.Unmarshal(jsonBytes, &commentsMap); err != nil {
		log.Fatalf("Failed to read JSON file: %v", err)
	}

	return commentsMap
}

func openFileOrDie(path string) *os.File {
	f, err := os.Open(path)
	if err != nil {
		log.Fatalf("Failed to open file: %v, path: %s", err, path)
	}
	return f
}

func closeFileOrDie(file *os.File) {
	if err := file.Close(); err != nil {
		log.Fatalf("Failed to close file: %v", err)
	}
}

// Checks whether a word is in a slice of strings (case-insensitive).
func inSlice(word string, arr []string) bool {
	for _, w := range arr {
		if strings.EqualFold(w, word) {
			return true
		}
	}
	return false
}
