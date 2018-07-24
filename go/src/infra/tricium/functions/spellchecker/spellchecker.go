// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"flag"
	"fmt"
	"infra/tricium/api/v1"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
)

// Paths to the required resources relative to the executable directory.
const (
	pythonPath           = "python/bin/python"
	codespellPath        = "codespell/bin/codespell"
	codespellPackagePath = "codespell/lib/python2.7/site-packages"
)

// The CodeSpell current output format is: {path}:{line}: {misspelling} ==> {fix}
// OR {path}:{line}: {misspelling} ==> {fix1}, {fix2}, ..., {fixN}
// OR {path}:{line}: {misspelling} ==> {fix1}, {fix2}, ..., {fixN}  | {reason}
const msgRegex = `^(.+?):([0-9]+): (.+)  ==> ([^,|]+)((, [^,|]+)*)(\| .+)?`

var whitelistWords = []string{"gae"}

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument")
	}

	// Retrieve the path name for the executable that started the current process.
	ex, err := os.Executable()
	if err != nil {
		log.Fatal(err)
	}
	exPath := filepath.Dir(ex)
	log.Printf("Using executable path: %s", exPath)

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %#v", input)

	results := &tricium.Data_Results{}
	for _, file := range input.Files {
		if !file.IsBinary {
			exPath = ""
			cmdName := filepath.Join(exPath, pythonPath)
			cmdArgs := []string{filepath.Join(exPath, codespellPath),
				filepath.Join(*inputDir, file.Path), "--quiet-level=3"}

			cmd := exec.Command(cmdName, cmdArgs...)
			log.Printf("Command: %#v; args: %#v", cmdName, cmdArgs)

			// Set PYTHONPATH for the command to run so that the bundled version of pylint and its dependencies are used.
			os.Setenv("PYTHONPATH", codespellPackagePath)

			stdoutPipe, err := cmd.StdoutPipe()
			if err != nil {
				fmt.Fprintln(os.Stderr, "Error creating StdoutPipe for Cmd", err)
				os.Exit(1)
			}

			p := file.Path
			f, err := os.Open(filepath.Join(*inputDir, p))
			if err != nil {
				log.Fatalf("Failed to open file: %v, path: %s", err, p)
			}
			defer func() {
				if err := f.Close(); err != nil {
					log.Fatalf("Failed to close file: %v, path: %s", err, p)
				}
			}()

			// Creates a Scanner from codespell's output to stdout.
			stdoutScanner := bufio.NewScanner(stdoutPipe)

			done := make(chan bool)
			go scanCodespellOutput(stdoutScanner, bufio.NewScanner(f), results, done)

			// CodeSpell will start producing output to stdout (and therefore to the scanner).
			if err = cmd.Start(); err != nil {
				fmt.Fprintln(os.Stderr, "Error starting Cmd", err)
				os.Exit(1)
			}

			// Halts until parsing the codespell output is completed.
			<-done
			cmd.Wait()
		}
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, results)
}

// scanCodespellOutput reads CodeSpell's output line by line and populates results.
func scanCodespellOutput(stdoutScanner *bufio.Scanner, fileScanner *bufio.Scanner, results *tricium.Data_Results, done chan bool) {
	currFileLine := 1
	lastReadLine := ""
	// Read line by line, adding comments to the output.
	for stdoutScanner.Scan() {
		line := stdoutScanner.Text()

		comment, currLine, readLine := parseCodespellLine(line, fileScanner, currFileLine, lastReadLine)

		// Update current line and last read line so that scanner can start counting from the appropriate line.
		currFileLine = currLine
		lastReadLine = readLine

		if comment == nil {
			log.Printf("SKIPPING %q", line)
		} else {
			log.Printf("ADDING   %q", line)
			results.Comments = append(results.Comments, comment)
		}
	}

	// Testing is done without a valid channel.
	if done != nil {
		done <- true
	}
}

// Parses one line of Codespell output to produce a comment.
//
// Returns the produced comment, the number of lines read in the file and the
// last line read from the file.
// Returns nil if the given line doesn't match the expected pattern.
// See the constant msgRegex defined above for the expected message format.
func parseCodespellLine(stdoutLine string, fileScanner *bufio.Scanner,
	currFileLine int, lastReadLine string) (*tricium.Data_Comment, int, string) {
	re := regexp.MustCompile(msgRegex)
	match := re.FindStringSubmatch(stdoutLine)
	if match == nil {
		return nil, currFileLine, ""
	}
	lineno, err := strconv.Atoi(match[2])
	if err != nil {
		return nil, currFileLine, ""
	}

	// Ignore whitelisted words (such as GAE) while using the same
	// default dictionary from CodeSpell (in case of updates).
	if isWhitelisted(match[3]) {
		log.Printf("IGNORING: %q is a whitelisted word.", match[3])
		return nil, currFileLine, ""
	}

	// Ignore words that have a reason to be disabled in the default CodeSpell dictionary.
	if len(match[7]) > 0 {
		log.Printf("IGNORING: %q has a reason to be disabled in the default CodeSpell dictionary.", match[3])
		return nil, currFileLine, ""
	}

	// If there are multiple misspellings on the same line, use the line from the previous
	// iteration rather than looking forward in the file.
	var fileLine string
	var linesRead int
	if lineno < currFileLine {
		fileLine = lastReadLine
	} else {
		fileLine, linesRead = getLineFromFile(fileScanner, currFileLine, lineno)
	}
	startChar, endChar := findWordInLine(match[3], fileLine)

	replacements := []string{match[4]}
	replacements = append(replacements, strings.Split(match[5], ", ")...)

	var validReplacements []string
	var suggestions []*tricium.Data_Suggestion
	for _, replacement := range replacements {
		if len(replacement) > 0 {
			// Get rid of trailing white space if word has only 1 suggestion and a reason.
			replacement = strings.TrimSpace(replacement)
			validReplacements = append(validReplacements, replacement)
			suggestions = append(suggestions, &tricium.Data_Suggestion{
				Description: fmt.Sprintf("Misspelling fix suggestion"),
				Replacements: []*tricium.Data_Replacement{
					{
						Path:        match[1],
						Replacement: replacement,
						StartLine:   int32(lineno),
						EndLine:     int32(lineno),
						StartChar:   int32(startChar),
						EndChar:     int32(startChar + len(replacement)),
					},
				},
			})
		}
	}

	return &tricium.Data_Comment{
		Path: match[1],
		Message: fmt.Sprintf("%q is a possible misspelling of: %s", match[3],
			strings.Join(validReplacements, ", ")),
		Category:    "SpellChecker",
		StartLine:   int32(lineno),
		EndLine:     int32(lineno),
		StartChar:   int32(startChar),
		EndChar:     int32(endChar),
		Suggestions: suggestions,
	}, currFileLine + linesRead, fileLine
}

// Given a line number, gets the line it corresponds to in a file.
//
// It is assumed that it will be called in order (since the scanner advances
// to the given line and cannot go back).
func getLineFromFile(fileScanner *bufio.Scanner, currLine int, lineno int) (string, int) {
	// Advance file pointer to specified line. The codespell output is ordered by line
	// numbers so no need to reset file scanner position.
	linesRead := 0
	for fileScanner.Scan() {
		linesRead++
		if currLine != lineno {
			currLine++
		} else {
			return fileScanner.Text(), linesRead
		}
	}

	// Could not find line in file.
	return "", linesRead
}

// Finds the character range of a word in a given line.
func findWordInLine(word string, line string) (int, int) {
	startChar := strings.Index(line, word)
	if startChar == -1 {
		return 0, 0
	}
	return startChar, startChar + len(word)
}

// Checks whether a word is in the whitelist (case-insensitive) in case it is a misspelling
// according to CodeSpell but is used frequently in the codebase i.e. GAE.
func isWhitelisted(word string) bool {
	for _, w := range whitelistWords {
		if strings.EqualFold(w, word) {
			return true
		}
	}
	return false
}
