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
	codespellPackagePath = "pylint/lib/python2.7/site-packages"
)

// The CodeSpell current output format is: {path}:{line}: {misspelling} ==> {fix}
// OR {path}:{line}: {misspelling} ==> {fix1}, {fix2}, ..., {fixN}
// OR {path}:{line}: {misspelling} ==> {fix1}, {fix2}, ..., {fixN}  | {reason}
const msgRegex = `^(.+?):([0-9]+): (.+)  ==> ([^,|]+)((, [^,|]+)*)(\| .+)?`

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
		panic(err)
	}
	exPath := filepath.Dir(ex)
	log.Printf("Using executable path: %s", exPath)

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %#v", input)

	// SpellChecker should only run on non-binary files.
	var files []*tricium.Data_File
	for _, file := range input.Files {
		if !file.IsBinary {
			files = append(files, file)
		}
	}

	results := &tricium.Data_Results{}
	for _, file := range input.Files {
		if !file.IsBinary {
			cmdName := filepath.Join(exPath, pythonPath)
			cmdArgs := []string{filepath.Join(exPath, codespellPath), filepath.Join(*inputDir, file.Path), "-q 3"}

			cmd := exec.Command(cmdName, cmdArgs...)
			log.Printf("Command: %#v; args: %#v", cmdName, cmdArgs)

			// Set PYTHONPATH for the command to run so that the bundled version of pylint and its dependencies are used.
			env := os.Environ()
			env = append(env, fmt.Sprintf("PYTHONPATH=%s", codespellPackagePath))
			cmd.Env = env

			stdoutPipe, err := cmd.StdoutPipe()
			if err != nil {
				fmt.Fprintln(os.Stderr, "Error creating StdoutPipe for Cmd", err)
				os.Exit(1)
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

			// Creates a Scanner from codespell's output to stdout.
			stdoutScanner := bufio.NewScanner(stdoutPipe)

			done := make(chan bool)
			go scanCodespellOutput(stdoutScanner, bufio.NewScanner(file), results, done)

			// CodeSpell will start producing output to stdout (and therefore to the scanner).
			err = cmd.Start()
			if err != nil {
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
	// Read line by line, adding comments to the output.
	for stdoutScanner.Scan() {
		line := stdoutScanner.Text()

		comment, currLine := parseCodespellLine(line, fileScanner, currFileLine)
		currFileLine = currLine // Update current line so that scanner can start counting from the appropriate line.
		if comment == nil {
			log.Printf("SKIPPING %q", line)
		} else {
			log.Printf("ADDING   %q", line)
			results.Comments = append(results.Comments, comment)
		}
	}

	// Testing is done without a valid channel
	if done != nil {
		done <- true
	}
}

// Parses one line of Codespell output to produce a comment.
//
// Returns nil if the given line doesn't match the expected pattern.
// See the constant msgRegex defined above for the expected message format.
func parseCodespellLine(stdoutLine string, fileScanner *bufio.Scanner, currFileLine int) (*tricium.Data_Comment, int) {
	re := regexp.MustCompile(msgRegex)
	match := re.FindStringSubmatch(stdoutLine)
	if match == nil {
		return nil, currFileLine
	}
	lineno, err := strconv.Atoi(match[2])
	if err != nil {
		return nil, currFileLine
	}

	replacements := []string{match[4]}
	replacements = append(replacements, strings.Split(match[5], ", ")...)

	var validReplacements []string
	for _, replacement := range replacements {
		if len(replacement) > 0 {
			// Get rid of trailing white space if word has only 1 suggestion and a reason.
			replacement = strings.TrimSpace(replacement)
			validReplacements = append(validReplacements, replacement)
		}
	}

	fileLine, linesRead := getLineFromFile(fileScanner, currFileLine, lineno)
	startChar, endChar := findWordInLine(match[3], fileLine)

	return &tricium.Data_Comment{
		Path: match[1],
		Message: fmt.Sprintf("%q is a possible misspelling of: %s", match[3],
			strings.Join(validReplacements, ", ")),
		Category:  "SpellChecker",
		StartLine: int32(lineno),
		StartChar: int32(startChar),
		EndChar:   int32(endChar),
	}, currFileLine + linesRead
}

func getLineFromFile(fileScanner *bufio.Scanner, currLine int, lineno int) (string, int) {
	// Advance file pointer to specified line. The output is ordered by line
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

func findWordInLine(word string, line string) (int, int) {
	startChar := strings.Index(line, word)
	if startChar == -1 {
		return startChar, -1
	}
	return startChar, startChar + len(word)
}
