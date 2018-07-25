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
)

// Paths to the required resources relative to the executable directory.
const (
	pythonPath  = "python/bin/python"
	cpplintPath = "cpplint.py"
)

// The cpplint current output format is: {path}:{line}: {msg}  [{category}/{symbol}] [{confidence}]
const msgRegex = `^(.+):([0-9]+):  (.+)  \[(.+)/(.+)\] \[([1-5])\]`

// TODO(diegomtzg): This parser is almost identical to the pylint parser, only differences are the regex,
// the fact that cpplint's output goes to stderr and the fact that cpplint's warnings don't have column numbers.
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
	exPath = ""
	log.Printf("Using executable path: %s", exPath)

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %#v", input)

	// TODO(diegomtzg): We could specify a certain type of comments to filter out.
	cmdName := filepath.Join(exPath, pythonPath)
	cmdArgs := []string{filepath.Join(exPath, cpplintPath)}
	for _, file := range input.Files {
		cmdArgs = append(cmdArgs, filepath.Join(*inputDir, file.Path))
	}
	cmd := exec.Command(cmdName, cmdArgs...)
	log.Printf("Command: %#v; args: %#v", cmdName, cmdArgs)

	// Cpplint prints warnings to stderr.
	stderrReader, err := cmd.StderrPipe()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error creating stderr for Cmd", err)
		os.Exit(1)
	}

	scanner := bufio.NewScanner(stderrReader)
	output := &tricium.Data_Results{}

	done := make(chan bool)
	go scanCpplintOutput(scanner, output, done)

	err = cmd.Start()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error starting Cmd", err)
		os.Exit(1)
	}

	<-done
	cmd.Wait()

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, output)
}

//  Reads cpplint's output line by line and populates results.
func scanCpplintOutput(scanner *bufio.Scanner, results *tricium.Data_Results, done chan bool) {
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

	// Testing is done without a valid channel.
	if done != nil {
		done <- true
	}
}

// Parses one line of cpplint output to produce a comment.
//
// Returns the produced comment or nil if the given line doesn't match the expected pattern.
// See the constant msgRegex defined above for the expected message format.
func parseCpplintLine(line string) *tricium.Data_Comment {
	re := regexp.MustCompile(msgRegex)
	match := re.FindStringSubmatch(line)
	if match == nil {
		return nil
	}
	lineno, err := strconv.Atoi(match[2])
	if err != nil {
		return nil
	}

	// TODO(diegomtzg): Consider only adding comments that have a high confidence.
	conf, err := strconv.Atoi(match[6])
	if err != nil {
		return nil
	}
	return &tricium.Data_Comment{
		Path:      match[1],
		Message:   fmt.Sprintf("%s | Confidence (1-5): %d", match[3], conf),
		Category:  fmt.Sprintf("Cpplint/%s/%s", match[4], match[5]),
		StartLine: int32(lineno),
	}
}
