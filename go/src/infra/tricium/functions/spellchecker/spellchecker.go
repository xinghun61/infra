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
	"regexp"
	"strings"

	"infra/tricium/api/v1"
)

type commentFormat struct {
	LineStart  string `json:"line_start"`
	BlockStart string `json:"block_start"`
	BlockEnd   string `json:"block_end"`
}

const (
	commentsJSONPath = "comment_formats.json"
	dictPath         = "dictionary.txt"
)

type state int

const (
	lineComment state = iota
	blockComment
	noComment
)

var (
	whitelistWords = []string{"gae"}
	textFileExts   = []string{".txt", ".md"}
	dict           map[string][]string

	// Define what counts as non-word characters.
	nonWord = regexp.MustCompile("[^a-zA-Z0-9'-]")
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
	log.Printf("Read FILES data: %#v", input)

	results := &tricium.Data_Results{}

	for _, file := range input.Files {
		if !file.IsBinary {
			p := filepath.Join(*inputDir, file.Path)

			f := openFileOrDie(p)
			defer closeFileOrDie(f)

			analyzeFile(bufio.NewScanner(f), p, results)
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, results)
}

// Analyzes file line by line to find misspellings within comments.
// TODO(diegomtzg): Add support for string literals.
func analyzeFile(scanner *bufio.Scanner, filePath string, results *tricium.Data_Results) {
	lineno := 1
	s := noComment
	fileExt := filepath.Ext(filePath)

	// TODO(qyearsley): Read dictionary and comment patterns once for all files,
	// and pass them in to this functionary (performance optimization).
	dict = buildDict()
	commentPatterns := getLangCommentPattern(fileExt)

	// The analyzer should check every word if the file is a text document.
	checkEveryWord := inSlice(fileExt, textFileExts)

	if commentPatterns == nil && !checkEveryWord {
		// If the file type is unknown, skip the file, since there may be
		// unknown source types that potentially have false positives.
		return
	}

	for scanner.Scan() {
		line := scanner.Text()

		// Note: Because we split the file lines by whitespace (to analyze each word), we don't
		// handle multi-word misspellings, although they do exist in the CodeSpell dictionary.
		for _, commentWord := range strings.Fields(line) {
			if checkEveryWord {
				var comments []*tricium.Data_Comment
				analyzeWords(line, commentWord, "", lineno, filePath, &comments)
				results.Comments = append(results.Comments, comments...)
			} else {
				comments := s.processCommentWord(line, commentWord, commentPatterns, lineno, filePath)
				results.Comments = append(results.Comments, comments...)
			}
		}

		// End of line, reset state if it is a single line comment.
		if s == lineComment {
			s = noComment
		}

		lineno++
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v, path: %s", err, filePath)
	}
}

// Process the given commentWord and change state appropriately depending on which
// comment characters are found in the given word. Returns the generated Tricium comments.
func (s *state) processCommentWord(line, commentWord string, commentPatterns *commentFormat,
	lineno int, filePath string) []*tricium.Data_Comment {
	var comments []*tricium.Data_Comment

	for i := 0; i < len(commentWord); {
		switch {
		case *s == lineComment:
			// Still in single-comment started in a previous word.
			i += analyzeWords(line, string(commentWord[i:]), "",
				lineno, filePath, &comments)
		case *s == blockComment && i+len(commentPatterns.BlockEnd) <= len(commentWord) &&
			string(commentWord[i:i+len(commentPatterns.BlockEnd)]) == commentPatterns.BlockEnd:
			// Currently in block comment and found end of block comment character.
			*s = noComment
			i += len(commentPatterns.BlockEnd)
		case *s == blockComment:
			// Still in block comment started in a previous line or word.
			i += analyzeWords(line, string(commentWord[i:]), commentPatterns.BlockEnd,
				lineno, filePath, &comments)
		case len(commentPatterns.LineStart) > 0 && i+len(commentPatterns.LineStart) <= len(commentWord) &&
			string(commentWord[i:i+len(commentPatterns.LineStart)]) == commentPatterns.LineStart:
			// Found single-line comment character.
			*s = lineComment
			stopIdx := analyzeWords(line, string(commentWord[i+len(commentPatterns.LineStart):]),
				"", lineno, filePath, &comments)
			i += len(commentPatterns.LineStart) + stopIdx
		case i+len(commentPatterns.BlockStart) <= len(commentWord) &&
			string(commentWord[i:i+len(commentPatterns.BlockStart)]) == commentPatterns.BlockStart:
			// Found block comment character.
			*s = blockComment
			stopIdx := analyzeWords(line, string(commentWord[i+len(commentPatterns.BlockStart):]),
				commentPatterns.BlockEnd, lineno, filePath, &comments)
			i += len(commentPatterns.BlockStart) + stopIdx
		default:
			// Don't start analyzing words until a comment character is found.
			i++
		}
	}

	return comments
}

// Checks words in a string which could contain multiple words separated by comment characters.
//
// Checks words until the state changes (e.g. we exit a comment). Returns the index after the
// word that caused the state to change so that calling function can continue from there.
func analyzeWords(line, commentWord, stopPattern string,
	lineno int, filePath string, comments *[]*tricium.Data_Comment) int {

	// If the current word does not contain the end of state pattern or if no end of state
	// pattern was specified, check the entire word/s for misspellings.
	stopIdx := strings.Index(commentWord, stopPattern)
	if stopIdx < 0 || stopPattern == "" {
		stopIdx = len(commentWord)
	}

	// Trim to only include parts of the word in current state.
	commentWord = string(commentWord[:stopIdx])

	// A single word (delimited by whitespace) could have multiple words delimited by
	// comment characters, so we split it by said characters and check the words individually.
	for _, wordToCheck := range strings.Fields(nonWord.ReplaceAllString(commentWord, " ")) {
		startChar, endChar := findWordInLine(wordToCheck, line)
		if fixes, ok := dict[strings.ToLower(wordToCheck)]; ok && !inSlice(wordToCheck, whitelistWords) {
			if c := buildMisspellingComment(wordToCheck, fixes, startChar, endChar,
				lineno, filePath); c != nil {
				*comments = append(*comments, c)
			}
		}
	}

	return stopIdx
}

// Finds the character range of a word in a given line.
func findWordInLine(word string, line string) (int, int) {
	startChar := strings.Index(line, word)
	if startChar == -1 {
		return 0, 0
	}
	return startChar, startChar + len(word)
}

// Helper function to convert misspelling information into a tricium comment.
func buildMisspellingComment(misspelling string, fixes []string, startChar int,
	endChar int, lineno int, path string) *tricium.Data_Comment {
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

	fixes = convertCaseOfFixes(misspelling, fixes)

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
		Path:        path,
		Message:     fmt.Sprintf("%q is a possible misspelling of %s.", misspelling, fixesMessage(fixes)),
		Category:    "SpellChecker",
		StartLine:   int32(lineno),
		EndLine:     int32(lineno),
		StartChar:   int32(startChar),
		EndChar:     int32(endChar),
		Suggestions: suggestions,
	}
}

// convertCaseOfFixes changes the case of all fixes to match the misspelling.
func convertCaseOfFixes(misspelling string, fixes []string) []string {
	var out []string
	for _, f := range fixes {
		out = append(out, matchCase(f, misspelling))
	}
	return out
}

// matchCase changes the case of a word to match the target.
//
// For example, if the misspelling in the text is "Coment", the dictionary will
// map "coment" to "comment", but when constructing the suggestion we'd like to
// propose replacing "Coment" with "Comment", so we want to convert the
// proposed fix to match the misspelling in the original text. The input word
// expected to always be all-lowercase.
func matchCase(word string, target string) string {
	if strings.ToUpper(target) == target {
		return strings.ToUpper(word)
	}
	if strings.Title(target) == target {
		return strings.Title(word)
	}
	return word
}

// fixesMessage constructs a string listing the possible fixes.
func fixesMessage(fixes []string) string {
	switch n := len(fixes); n {
	case 0:
		return "<nothing>"
	case 1:
		return fmt.Sprintf("%q", fixes[0])
	case 2:
		return fmt.Sprintf("%q or %q", fixes[0], fixes[1])
	default:
		var b strings.Builder
		for i := 0; i < n-1; i++ {
			fmt.Fprintf(&b, "%q, ", fixes[i])
		}
		fmt.Fprintf(&b, "or %q", fixes[n-1])
		return b.String()
	}
}

// Gets the appropriate comment pattern for the programming language determined by the given
// file extension.
func getLangCommentPattern(fileExt string) *commentFormat {
	commentFmtMap := loadCommentsJSONFile()
	return commentFmtMap[fileExt]
}

// buildDict constructs a map of misspellings to slices of proposed fixes.
//
// All keys in the dictionary are lower-case.
func buildDict() map[string][]string {
	f := openFileOrDie(dictPath)
	defer closeFileOrDie(f)

	dictMap := make(map[string][]string)
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()

		// Lines in the CodeSpell dictionary look like:
		// "{misspelling}->{fix1, fix2, ...} with the last one
		// being an optional reason to disable the word.
		parts := strings.Split(line, "->")
		fixes := strings.Split(parts[1], ", ")
		dictMap[strings.ToLower(parts[0])] = fixes
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v, path: %s", err, dictPath)
	}

	return dictMap
}

// Helper function to load the JSON file containing the currently supported file extensions
// and their respective comment formats.
func loadCommentsJSONFile() map[string]*commentFormat {
	var commentsMap map[string]*commentFormat

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
