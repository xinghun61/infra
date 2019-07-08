// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"flag"
	"fmt"
	tricium "infra/tricium/api/v1"
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
	pythonPath  = "python/bin/python"
	cpplintPath = "cpplint.py"
)

// Format: {path}:{line}: {msg}  [{category}/{symbol}] [{confidence}]
var msgRegex = regexp.MustCompile(`^(.+):([0-9]+):  (.+)  \[(.+)/(.+)\] \[([1-5])\]`)

// TODO(crbug/873202): This parser is almost identical to the pylint parser,
// some common parts might be extracted.
func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	filterFlag := flag.String("filter", "", "Comma-separated list of checks to filter")
	verboseFlag := flag.String("verbose", "", "Confidence filter, 1-5")
	rootFlag := flag.String("root", "", "Path to repo root, for header-guard paths")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}

	// Retrieve the path name for the executable that started the current
	// process, so that we can build an absolute path below.
	ex, err := os.Executable()
	if err != nil {
		log.Fatal(err)
	}
	exPath := filepath.Dir(ex)
	log.Printf("Using executable path %q.", exPath)

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err = tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	// Cpplint header guard paths are based on the path from the root of the
	// repo. For Tricium analyzers with FILES data, we don't actually have a
	// repository, just a collection of files.
	//
	// As a hack, to tell cpplint where the root of the repository should be,
	// we can call git init in the input directory.
	cmd := exec.Command("git", "init")
	cmd.Dir = *inputDir
	log.Printf("Running cmd: %s", cmd.Args)
	if err = cmd.Run(); err != nil {
		log.Fatalf("Failed to run command %s", err)
	}

	// Construct Command to run.
	cmdName := filepath.Join(exPath, pythonPath)
	cmdArgs := []string{
		filepath.Join(exPath, cpplintPath),
		"--filter", filterArg(*filterFlag),
		"--verbose", verboseArg(*verboseFlag),
	}
	if *rootFlag != "" {
		cmdArgs = append(cmdArgs, "--root", *rootFlag)
	}
	for _, file := range input.Files {
		cmdArgs = append(cmdArgs, file.Path)
	}
	cmd = exec.Command(cmdName, cmdArgs...)
	cmd.Dir = *inputDir
	log.Printf("Command: %s", cmd.Args)

	// Cpplint prints warnings to stderr.
	stderrReader, err := cmd.StderrPipe()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error creating stderr for Cmd.", err)
		os.Exit(1)
	}

	if err = cmd.Start(); err != nil {
		fmt.Fprintln(os.Stderr, "Error starting Cmd", err)
		os.Exit(1)
	}
	scanner := bufio.NewScanner(stderrReader)
	output := &tricium.Data_Results{}
	scanCpplintOutput(scanner, output)

	// A non-zero exit status for Cpplint doesn't mean that an error occurred,
	// it just means that warnings were found, so we don't need to look at the
	// error returned by Wait.
	cmd.Wait()

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to %q.", path)
}

func verboseArg(verboseFlag string) string {
	if verboseFlag != "" {
		return verboseFlag
	}
	return "4"
}

func filterArg(filterFlag string) string {
	if filterFlag != "" {
		return filterFlag
	}
	filters := []string{
		"-whitespace",
	}
	return strings.Join(filters, ",")
}

// Reads the output of cpplint line by line and populates the results.
func scanCpplintOutput(scanner *bufio.Scanner, results *tricium.Data_Results) {
	// Read line by line, adding comments to the output.
	for scanner.Scan() {
		line := scanner.Text()

		comment := parseCpplintLine(line)
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

// Parses one line of cpplint output to produce a comment.
//
// Returns the produced comment or nil if the given line doesn't match the
// expected pattern. See the constant msgRegex defined above for the expected
// message format.
func parseCpplintLine(line string) *tricium.Data_Comment {
	match := msgRegex.FindStringSubmatch(line)
	if match == nil {
		return nil
	}
	lineno, err := strconv.Atoi(match[2])
	if err != nil {
		return nil
	}
	message := match[3]
	category := match[4] + "/" + match[5]
	confidence, err := strconv.Atoi(match[6])

	if err != nil {
		return nil
	}

	if strings.Contains(message, "Add #include <string>") {
		// Relatively likely to be a false positive; https://crbug.com/936259.
		return nil
	}
	if category == "build/include_what_you_use" {
		message += ("\nNote: This check is known to produce false positives, " +
			"(e.g. for types used only in function overrides).")
	}

	return &tricium.Data_Comment{
		Path: match[1],
		Message: fmt.Sprintf(
			"%s (confidence %d/5).\nTo disable, add: // NOLINT(%s)",
			message, confidence, category),
		Category:  "Cpplint/" + category,
		StartLine: int32(lineno),
	}
}
