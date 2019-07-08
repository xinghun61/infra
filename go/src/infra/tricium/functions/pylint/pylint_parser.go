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

	tricium "infra/tricium/api/v1"
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
	disable := flag.String("disable", "", "Comma-separated list of checks "+
		"or categories of checks to disable.")
	enable := flag.String("enable", "", "Comma-separated checks "+
		"or categories of checks to enable. "+
		"The enable list overrides the disable list.")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}

	// Retrieve the path name for the executable that started the current process.
	ex, err := os.Executable()
	if err != nil {
		panic(err)
	}
	exPath := filepath.Dir(ex)
	log.Printf("Using executable path %q.", exPath)

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err = tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	// Filter the files to include only .py files.
	files, err := tricium.FilterFiles(input.Files, "*.py")
	if err != nil {
		log.Fatalf("Failed to filter files: %v", err)
	}

	// Construct the command args and invoke Pylint on the given paths.
	cmdName := filepath.Join(exPath, pythonPath)
	cmdArgs := []string{
		filepath.Join(exPath, pylintPath),
		"--rcfile", filepath.Join(exPath, "pylintrc"),
		"--msg-template", msgTemplate,
	}
	// With Pylint, the order of the disable and enable command line flags is
	// important; the later flags override previous flags. But for this
	// executable, the order is unimportant, the "enable" flag is always put
	// after "disable", so it always takes precedence.
	if *disable != "" {
		cmdArgs = append(cmdArgs, "--disable", *disable)
	}
	if *enable != "" {
		cmdArgs = append(cmdArgs, "--enable", *enable)
	}
	// In the output, we want relative paths from the repository root, which
	// will be the same as relative paths from the input directory root.
	for _, file := range files {
		cmdArgs = append(cmdArgs, filepath.Join(*inputDir, file.Path))
	}
	cmd := exec.Command(cmdName, cmdArgs...)
	log.Printf("Command: %s", cmd.Args)

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

	if err = cmd.Start(); err != nil {
		fmt.Fprintln(os.Stderr, "Error starting Cmd.", err)
		os.Exit(1)
	}
	scanner := bufio.NewScanner(stdoutReader)
	output := &tricium.Data_Results{}
	scanPylintOutput(scanner, output)

	// A non-zero exit status for Pylint doesn't mean that an error occurred,
	// it just means that warnings were found, so we don't need to look at the
	// error returned by Wait.
	cmd.Wait()

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

// scanPylintOutput reads Pylint output line by line and populates results.
func scanPylintOutput(scanner *bufio.Scanner, results *tricium.Data_Results) {
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
	category, symbol, message := match[4], match[5], match[6]
	if symbol == "undefined-variable" {
		message = (message + ".\n" +
			"This check could give false positives when there are wildcard imports\n" +
			"(from module import *). It is recommended to avoid wildcard imports; see\n" +
			"https://www.python.org/dev/peps/pep-0008/#imports")
	}
	return &tricium.Data_Comment{
		Path:      match[1],
		Message:   fmt.Sprintf("%s.\nTo disable, add: # pylint: disable=%s", message, symbol),
		Category:  fmt.Sprintf("Pylint/%s/%s", category, symbol),
		StartLine: int32(lineno),
		StartChar: int32(column),
	}
}
