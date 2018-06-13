// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"

	"infra/tricium/api/v1"
)

// The Pylint output format is adjustable, for details see
// https://docs.pylint.org/en/1.6.0/output.html
// The current format is {path}:{line}:{column} [{category}/{symbol}] {msg}
const msgRegex = `^(.+?):([0-9]+):([0-9]+) \[(.+)/(.+)\] (.+)$`

// Paths to the required resources relative to the executable directory.
const (
	pythonPath = "python/bin/python"
	pylintPath = "pylint/bin/pylint"
)

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

	// Invoke Pylint on the given paths.
	// In the output, we want relative paths from the repository root, which
	// will be the same as relative paths from the input directory root.
	cmdName := filepath.Join(exPath, pythonPath)
	cmdArgs := []string{filepath.Join(exPath, pylintPath), "--rcfile",
		filepath.Join(exPath, "pylintrc")}
	for _, file := range input.Files {
		cmdArgs = append(cmdArgs, filepath.Join(*inputDir, file.Path))
	}
	cmd := exec.Command(cmdName, cmdArgs...)
	log.Printf("Command args: %#v", cmdArgs)

	cmdReader, err := cmd.StdoutPipe()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error creating StdoutPipe for Cmd", err)
		os.Exit(1)
	}

	// Creates a scanner from pylint's output to stdout.
	scanner := bufio.NewScanner(cmdReader)
	output := &tricium.Data_Results{}

	// Prepare to parse the pylint output in a separate goroutine in case it is very large.
	done := make(chan bool)
	go scanPylintOutput(scanner, output, done)

	// Pylint will start producing output to stdout (and therefore to the scanner).
	err = cmd.Start()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error starting Cmd", err)
		os.Exit(1)
	}

	// Halts until parsing the pylint output has finished, making sure that all the data
	// has been read from stdout (preventing race conditions/non-determinism).
	// From the golang exec documentation: "It is incorrect to call Wait before
	// all reads from the pipe have completed".
	<-done

	// A non-zero exit status for Pylint doesn't mean that an error occurred, so we don't
	// need to look at the error returned by Wait.
	cmd.Wait()

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, output)
}

// scanPylintOutput reads Pylint output line by line and populates results.
//
// It must notify the calling function when it is done by sending true into the done channel.
func scanPylintOutput(scanner *bufio.Scanner, results *tricium.Data_Results, done chan bool) {
	// Read line by line, adding comments to the output.
	for scanner.Scan() {
		line := scanner.Text()
		comment := parsePylintLine(line)
		if comment == nil {
			log.Printf("Skipping line %#v\n", line)
		}
		if comment != nil {
			results.Comments = append(results.Comments, comment)
		}
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v", err)
	}

	// Testing is done without a valid channel
	if done != nil {
		done <- true
	}
}

// parsePylintLine parses one line of Pylint output to produce a comment.
//
// Returns nil if the given line doesn't match the expected pattern.
// See the constant msgRegex defined above for the expected message format.
func parsePylintLine(line string) *tricium.Data_Comment {
	re := regexp.MustCompile(msgRegex)
	match := re.FindStringSubmatch(line)
	if match == nil {
		return nil
	}
	lineno, err := strconv.Atoi(match[2])
	if err != nil {
		return nil
	}
	column, err := strconv.Atoi(match[3])
	if err != nil {
		return nil
	}
	return &tricium.Data_Comment{
		Path:      match[1],
		Message:   match[6],
		Category:  fmt.Sprintf("Pylint/%s/%s", match[4], match[5]),
		StartLine: int32(lineno),
		StartChar: int32(column),
	}
}
