// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"infra/tricium/api/v1"
)

// Paths to the required resources relative to the executable directory.
const (
	nodePath   = "node/bin/node"
	eslintPath = "eslint/bin/eslint.js"
)

var severityLevels = []string{"warning", "error"}

// Message is the structure of ESLint error messages.
type Message struct {
	RuleID    string
	Message   string
	Line      int32
	Column    int32
	EndLine   int32
	Severity  int32
	EndColumn int32
}

// FileErrors is the parent structure of ESLint errors for every file.
type FileErrors struct {
	FilePath     string
	Messages     []Message
	ErrorCount   int32
	WarningCount int32
}

// TODO(crbug/873202): This parser is almost identical to the pylint parser,
// some common parts might be extracted.
func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
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

	// Filter the files to include only .js files.
	files, err := tricium.FilterFiles(input.Files, "*.js")
	if err != nil {
		log.Fatalf("Failed to filter files: %v", err)
	}

	cmdName := filepath.Join(exPath, nodePath)
	cmdArgs := []string{
		filepath.Join(exPath, eslintPath),
		"-f", "json",
	}
	for _, file := range files {
		cmdArgs = append(cmdArgs, filepath.Join(*inputDir, file.Path))
	}
	cmd := exec.Command(cmdName, cmdArgs...)
	log.Printf("Command: %#v; args: %#v", cmdName, cmdArgs)

	stdoutReader, err := cmd.StdoutPipe()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Error creating StdoutPipe for Cmd", err)
		os.Exit(1)
	}

	// Creates a scanner from ESLint's output to stdout.
	scanner := bufio.NewScanner(stdoutReader)
	output := &tricium.Data_Results{}

	// Prepare to parse the ESLint output in a separate goroutine in case it is
	// very large.
	done := make(chan bool)
	go scanEslintOutput(scanner, output, done)

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

// scanEslintOutput reads ESLint output and populates results.
//
// It must notify the calling function when it is done by sending true into the
// done channel.
func scanEslintOutput(scanner *bufio.Scanner, results *tricium.Data_Results, done chan bool) {
	// Read line by line, adding comments to the output.
	scanner.Scan()
	if err := scanner.Err(); err != nil {
		log.Fatalf("Failed to read command output: %v", err)
	}

	jsonOutput := strings.TrimSpace(scanner.Text())
	var output []FileErrors

	fmt.Println(jsonOutput)

	if err := json.Unmarshal([]byte(jsonOutput), &output); err != nil {
		log.Fatalf("Failed to parse JSON output: %v", err)
	}

	for _, fileOutput := range output {
		filePath := fileOutput.FilePath
		for _, message := range fileOutput.Messages {
			if comment := makeCommentForMessage(filePath, message); comment != nil {
				results.Comments = append(results.Comments, comment)
			}
		}
	}

	if done != nil {
		done <- true
	}
}

// makeCommentForMessage constructs a Tricium comment from one message.
func makeCommentForMessage(path string, message Message) *tricium.Data_Comment {
	return &tricium.Data_Comment{
		Path:      path,
		Message:   fmt.Sprintf("%s\nTo disable, add: // eslint-disable-line %s", message.Message, message.RuleID),
		Category:  fmt.Sprintf("ESLint/%s/%s", severityLevels[message.Severity-1], message.RuleID),
		StartLine: message.Line,
		StartChar: message.Column,
		EndChar:   message.EndColumn,
		EndLine:   message.EndLine,
	}
}
