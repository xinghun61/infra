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
	"unicode"

	tricium "infra/tricium/api/v1"
)

// commentFormat is the expected format for the commentsJSONPath file.
type commentFormat struct {
	LineStart  string `json:"line_start"`
	BlockStart string `json:"block_start"`
	BlockEnd   string `json:"block_end"`
}

// wordSegment contains the individual word and its starting index in parent word.
type wordSegment struct {
	word       string
	startIndex int
}

const (
	commentsJSONPath = "comment_formats.json"
	dictPath         = "dictionary.txt"
)

// state is the comment processing state machine.
type state int

const (
	lineComment state = iota
	blockComment
	noComment
)

var (
	// ignoredWords are words that shouldn't be flagged, even if they appear in
	// the dictionary.
	ignoredWords = []string{
		"als",         // abbr. for ambient light sensor
		"backed",      // as in "backed by"
		"cant",        // contraction, may appear in variable names, also a word
		"cas",         // abbr. for Content Addressed Storage
		"copyable",    // Valid usage, and used in C++, e.g. is_trivially_copyable
		"crasher",     // something that causes a crash
		"crate",       // Rust keyword
		"dont",        // contraction, may appear in variable names
		"ect",         // abbr. for effective connection time
		"files'",      // possessive of files
		"gae",         // abbr. for Google App Engine
		"hist",        // abbr. for histogram
		"ith",         // ordinal form of variable i, like nth
		"lightening",  // present participle of "to lighten"
		"mut",         // Rust keyword
		"process'",    // possessive of process
		"seeked",      // JS event
		"subprocess'", // possessive of subprocess
		"tast",        // Name of a ChromeOS test
		"wont",        // contraction, may appear in variable names, also a word
		"wontfix",     // Monorail bug status
	}
	textFileExts = []string{".txt", ".md"}

	// TODO(qyearsley): Pass around a dict instead of using a global variable.
	dict map[string][]string

	// Selects word characters and other characters that shouldn't split words.
	// Apostrophes and dashes can be considered part of words, as well as
	// non-ASCII letters, e.g. é, ç, etc. and digits. Other non-letter Unicode
	// characters don't need to be considered, as they won't appear mixed
	// inside English words and also won't appear in the dictionary of English
	// misspellings.
	// See https://golang.org/s/re2syntax for the regexp syntax reference.
	justWord = regexp.MustCompile(`[\p{L}\d'_-]+`)

	// Patterns that indicate we don't want to flag misspellings. To prevent
	// false positives, we also match when there are prefixes or suffixes.
	emailPattern = regexp.MustCompile(`\w+@\w+\.\w+`)
	urlPattern   = regexp.MustCompile(`https?:\/\/\S+`)
	todoPattern  = regexp.MustCompile(`TODO\S*`)

	// selects everything except whitespace.
	whitespaceBreak = regexp.MustCompile(`[^\s]+`)
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}
	cp := loadCommentsJSONFile()
	dict = loadDictionaryFile()

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	results := &tricium.Data_Results{}

	for _, file := range input.Files {
		if !file.IsBinary {
			fileExt := filepath.Ext(file.Path)
			// The analyzer should check every word if the file is a text document.
			checkEveryWord := inSlice(fileExt, textFileExts)
			patterns := cp[fileExt]
			if patterns == nil && !checkEveryWord {
				// If the file type is unknown, skip the file, since there may be
				// unknown source types that potentially have false positives.
				continue
			}

			p := filepath.Join(*inputDir, file.Path)
			f := openFileOrDie(p)
			analyzeFile(bufio.NewScanner(f), p, checkEveryWord, patterns, results)
			closeFileOrDie(f)
		}
	}

	// Also check the commit message.
	analyzeFile(bufio.NewScanner(strings.NewReader(input.CommitMessage)), "", true, nil, results)

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

// Analyzes file line by line to find misspellings within comments.
func analyzeFile(scanner *bufio.Scanner, path string, checkEveryWord bool, patterns *commentFormat, results *tricium.Data_Results) {
	lineNum := 1
	s := noComment

	for scanner.Scan() {
		line := scanner.Text()

		// Note: Because we split words in the line by whitespace, we don't
		// handle multi-word misspellings, although they could exist in the
		// codespell dictionary.
		for _, bounds := range whitespaceBreak.FindAllStringIndex(line, -1) {
			startIdx, endIdx := bounds[0], bounds[1]
			var comments []*tricium.Data_Comment
			commentWord := line[startIdx:endIdx]

			if checkEveryWord {
				analyzeWords(commentWord, "", lineNum, startIdx, path, &comments)
				results.Comments = append(results.Comments, comments...)
			} else {
				s.processCommentWord(commentWord, patterns, lineNum, startIdx, path, &comments)
				results.Comments = append(results.Comments, comments...)
			}
		}

		// End of line; reset state if it is a single line comment.
		if s == lineComment {
			s = noComment
		}

		lineNum++
	}
	if err := scanner.Err(); err != nil {
		log.Printf("Failed to read a line, skipping the rest of %q: %v", path, err)
	}
}

// processCommentWord processes a "word" string in a comment.
//
// Here, the input word is a string with no whitespace, but it may contain
// special characters such as punctuation, e.g. it could be "foo//bar*/--" but
// it could not be "foo bar".
//
// Depending on whether special comment characters are found in the string,
// processCommentWord may change the state. If potential misspellings are
// found, this function will add Tricium comments the given comments slice.
func (s *state) processCommentWord(word string, patterns *commentFormat,
	lineno, startIdx int, path string, comments *[]*tricium.Data_Comment) {
	for i := 0; i < len(word); {
		switch {
		case *s == lineComment:
			// In single-line comment.
			i += analyzeWords(string(word[i:]), "", lineno, startIdx+i, path, comments)
		case (*s == blockComment && i+len(patterns.BlockEnd) <= len(word) &&
			string(word[i:i+len(patterns.BlockEnd)]) == patterns.BlockEnd):
			// Currently in block comment and found end of block comment character.
			*s = noComment
			i += len(patterns.BlockEnd)
		case *s == blockComment:
			// In block comment.
			i += analyzeWords(string(word[i:]), patterns.BlockEnd, lineno, startIdx+i, path, comments)
		case (len(patterns.LineStart) > 0 && i+len(patterns.LineStart) <= len(word) &&
			string(word[i:i+len(patterns.LineStart)]) == patterns.LineStart):
			// Found start of single-line comment.
			*s = lineComment
			stopIdx := analyzeWords(
				string(word[i+len(patterns.LineStart):]), "", lineno,
				startIdx+i+len(patterns.LineStart), path, comments)
			i += len(patterns.LineStart) + stopIdx
		case (len(patterns.BlockStart) > 0 && i+len(patterns.BlockStart) <= len(word) &&
			string(word[i:i+len(patterns.BlockStart)]) == patterns.BlockStart):
			// Found start of block comment.
			*s = blockComment
			stopIdx := analyzeWords(
				string(word[i+len(patterns.BlockStart):]), patterns.BlockEnd,
				lineno, startIdx+i+len(patterns.BlockStart), path, comments)
			i += len(patterns.BlockStart) + stopIdx
		default:
			// Not in a comment. Don't start analyzing words until a comment
			// start pattern is found.
			i++
		}
	}
}

// Checks words in a string which could contain multiple words separated by
// comment characters.
//
// For example, the input word could be "foo*/bar", so in order to check
// only word in comments we would want to check "foo" but not "bar".
//
// Checks words until the state changes (e.g. we exit a comment). Returns the
// index after the word that caused the state to change so that calling
// function can continue from there.
func analyzeWords(commentWord, stopPattern string,
	lineno, startIdx int, path string, comments *[]*tricium.Data_Comment) int {
	// If the current word does not contain the end of state pattern or if no
	// end of state pattern was specified, check the entire word (or words) for
	// misspellings.
	stopIdx := strings.Index(commentWord, stopPattern)
	if stopIdx < 0 || stopPattern == "" {
		stopIdx = len(commentWord)
	}

	// Trim to only include parts of the word in current (comment) state.
	commentWord = string(commentWord[:stopIdx])

	// There are places where checking spelling leads to relatively high
	// false positives: URLs, email addresses, and TODO notes. In these
	// cases, just skip the word.
	if urlPattern.MatchString(commentWord) || emailPattern.MatchString(commentWord) || todoPattern.MatchString(commentWord) {
		return stopIdx
	}

	// A single word (delimited by whitespace) could have multiple words
	// delimited by comment characters, so we split it by said characters and
	// check the words individually.
	for _, wordToCheckSplit := range splitComment(commentWord) {
		wordToCheck := wordToCheckSplit.word

		// Words that are all upper-case are likely to be initialisms,
		// which are more likely to be false positives because they usually
		// aren't real words, and may be constant identifiers.
		if wordToCheck == strings.ToUpper(wordToCheck) {
			continue
		}

		// Check if the word is in the ignore list (even if camelcased).
		if inSlice(strings.ToLower(wordToCheck), ignoredWords) {
			continue
		}

		// Split at uppercase letters to handle camel cased words.
		for _, currentWordSegment := range splitCamelCase(wordToCheck) {
			word := currentWordSegment.word
			if fixes, ok := dict[strings.ToLower(word)]; ok && !inSlice(word, ignoredWords) {
				if c := buildMisspellingComment(word, fixes,
					startIdx+wordToCheckSplit.startIndex+currentWordSegment.startIndex, lineno, path); c != nil {
					*comments = append(*comments, c)
				}
			}
		}
	}

	return stopIdx
}

// Helper function to convert misspelling information into a Tricium comment.
func buildMisspellingComment(misspelling string, fixes []string, startIdx, lineno int, path string) *tricium.Data_Comment {
	// If there is more than one fix and the last character of the last element
	// of fixes doesn't have a comma, the word has a reason to be disabled.
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
					StartChar:   int32(startIdx),
					EndChar:     int32(startIdx + len(misspelling)),
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
		StartChar:   int32(startIdx),
		EndChar:     int32(startIdx + len(misspelling)),
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
	if capitalize(target) == target {
		return capitalize(word)
	}
	return word
}

// capitalize just changes the first letter to title case.
//
// This is almost the same as strings.Title but only ever changes the first
// letter; strings.Title would convert "don't" to "Don'T", whereas this
// function would return "Don't".
func capitalize(word string) string {
	if len(word) == 0 {
		return ""
	}
	runes := []rune(word)
	runes[0] = unicode.ToTitle(runes[0])
	return string(runes)
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

// loadDictionaryFile reads the dictionary file and constructs a map of
// misspellings to slices of proposed fixes.
//
// All keys in the dictionary are lower-case.
func loadDictionaryFile() map[string][]string {
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

		// Remove any instances of the misspelling from the suggested fixes.
		for i := len(fixes) - 1; i >= 0; i-- {
			tok := strings.Trim(fixes[i], ",")

			// If the suggestion matches the misspelling, omit it.
			if tok == parts[0] {
				fixes = append(fixes[:i], fixes[i+1:]...)
			}
		}

		dictMap[strings.ToLower(parts[0])] = fixes
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v, path: %s", err, dictPath)
	}

	return dictMap
}

// loadCommentsJSONFile loads the JSON file containing the currently supported
// file extensions and their respective comment formats.
func loadCommentsJSONFile() map[string]*commentFormat {
	var commentsMap map[string]*commentFormat

	f := openFileOrDie(commentsJSONPath)
	defer closeFileOrDie(f)

	jsonBytes, err := ioutil.ReadAll(f)
	if err != nil {
		log.Fatalf("Failed to read JSON file: %v", err)
	}
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

func closeFileOrDie(f *os.File) {
	if err := f.Close(); err != nil {
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

// Splits a string, which may be delimited by punctuation but not whitespace,
// into individual words.
func splitComment(commentWord string) []wordSegment {
	var segments []wordSegment
	for _, wordIndex := range justWord.FindAllStringIndex(commentWord, -1) {
		segments = append(segments,
			wordSegment{commentWord[wordIndex[0]:wordIndex[1]], wordIndex[0]})
	}
	return segments
}

// Splits a camel-cased word into individual words.
func splitCamelCase(word string) []wordSegment {
	var segments []wordSegment
	wordStart := 0
	for wordEnd, letter := range word {
		if wordEnd != 0 && unicode.IsUpper(letter) {
			segments = append(segments, wordSegment{word[wordStart:wordEnd], wordStart})
			wordStart = wordEnd
		}
	}
	segments = append(segments, wordSegment{word[wordStart:], wordStart})
	return segments
}
