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

// The pylint output format specification.
// See: https://docs.pylint.org/en/1.6.0/output.html
const msgTemplate = "{path}:{line}:{column} [{category}/{symbol}] {msg}"

// The related regexp for parsing the above output format.
var msgRegex = regexp.MustCompile(`^(.+?):([0-9]+):([0-9]+) \[(.+)/(.+)\] (.+)$`)

// Paths to the required resources relative to the executable directory.
const (
	pythonPath        = "python/bin/python"
	pylintPath        = "pylint/bin/pylint"
	pylintPackagePath = "pylint/lib/python2.7/site-packages"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	enable := flag.String("enable", "", "Comma-separated list of checks to enable")
	disable := flag.String("disable", "", "Comma-separated list of checks to disable")
	// TODO(qyearsley): Add flags for disabling/enabling warnings; this
	// would enable specifying warnings in project configs.
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

	// Filter the files to include only .py files.
	files, err := tricium.FilterFiles(input.Files, "*.py")
	if err != nil {
		log.Fatalf("Failed to filter files: %v", err)
	}

	// Invoke Pylint on the given paths.
	// In the output, we want relative paths from the repository root, which
	// will be the same as relative paths from the input directory root.
	cmdName := filepath.Join(exPath, pythonPath)
	cmdArgs := []string{
		filepath.Join(exPath, pylintPath),
		"--rcfile", filepath.Join(exPath, "pylintrc"),
		"--msg-template", msgTemplate,
		"--enable", *enable,
		"--disable", *disable,
	}
	for _, file := range files {
		cmdArgs = append(cmdArgs, filepath.Join(*inputDir, file.Path))
	}
	cmd := exec.Command(cmdName, cmdArgs...)
	log.Printf("Command: %#v; args: %#v", cmdName, cmdArgs)

	// Set PYTHONPATH for the command to run so that the bundled version of
	// pylint and its dependencies are used.
	env := os.Environ()
	env = append(env, fmt.Sprintf("PYTHONPATH=%s", pylintPackagePath))
	cmd.Env = env

	stdoutReader, err := cmd.StdoutPipe()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error creating StdoutPipe for Cmd", err)
		os.Exit(1)
	}

	// Creates a scanner from pylint's output to stdout.
	scanner := bufio.NewScanner(stdoutReader)
	output := &tricium.Data_Results{}

	// Prepare to parse the pylint output in a separate goroutine in case it is
	// very large.
	done := make(chan bool)
	go scanPylintOutput(scanner, output, done)

	// Pylint will start producing output to stdout, and therefore to the
	// scanner.
	err = cmd.Start()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error starting Cmd", err)
		os.Exit(1)
	}

	// Halts until parsing the pylint output has finished, making sure that all
	// the data has been read from stderr, preventing race conditions or
	// non-determinism. See: https://golang.org/pkg/os/exec/#Cmd.StderrPipe.
	<-done

	// A non-zero exit status for Pylint doesn't mean that an error occurred,
	// so we don't need to look at the error returned by Wait.
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
// It must notify the calling function when it is done by sending true into the
// done channel.
func scanPylintOutput(scanner *bufio.Scanner, results *tricium.Data_Results, done chan bool) {
	// Read line by line, adding comments to the output.
	for scanner.Scan() {
		line := scanner.Text()

		comment := parsePylintLine(line)
		if comment == nil {
			log.Printf("SKIPPING %q", line)
		} else {
			log.Printf("ADDING   %q", line)
			results.Comments = append(results.Comments, comment)
		}
	}
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read file: %v", err)
	}

	// Testing may be done without without a valid channel.
	// TODO(qyearsley): Add valid channel in tests.
	if done != nil {
		done <- true
	}
}

// parsePylintLine parses one line of Pylint output to produce a comment.
//
// Returns nil if the given line doesn't match the expected pattern.
func parsePylintLine(line string) *tricium.Data_Comment {
	match := msgRegex.FindStringSubmatch(line)
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
		Message:   fmt.Sprintf("%s.\nTo disable, add: # pylint: disable=%s", match[6], match[5]),
		Category:  fmt.Sprintf("Pylint/%s/%s", match[4], match[5]),
		StartLine: int32(lineno),
		StartChar: int32(column),
	}
}
