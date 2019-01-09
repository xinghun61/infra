// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the Git File Isolator analyzer.
package main

import (
	"flag"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"

	"infra/tricium/api/v1"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()

	// Read Tricium input GIT_FILE_DETAILS data.
	input := &tricium.Data_GitFileDetails{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Fatalf("Failed to read GIT_FILE_DETAILS data: %v", err)
	}
	log.Printf("Read GIT_FILE_DETAILS data.")

	// Set up temporary directory.
	tempDir, err := ioutil.TempDir("", "git-file-isolator")
	if err != nil {
		log.Fatalf("Failed to setup temporary directory: %v", err)
	}

	// Clean up.
	defer func() {
		if err := os.RemoveAll(tempDir); err != nil {
			log.Fatalf("Failed to clean up temporary directory %q: %v", tempDir, err)
		}
	}()
	log.Printf("Created temporary directory %q.", tempDir)

	// Check out files from the given git ref.
	cmds := []*exec.Cmd{
		exec.Command("git", "init"),
		exec.Command("git", "fetch", "--depth=1", "--no-tags",
			"--no-recurse-submodules", input.Repository, input.Ref),
		exec.Command("git", "checkout", "FETCH_HEAD", "--"),
	}

	// Explicitly add the list of files to the command line to checkout
	// to speed things up.
	// NB! The max length for a command line supported by the OS may be
	// exceeded; the max length for command line on POSIX can be inspected
	// with `getconf ARG_MAX`.
	// TODO(qyearsley): In order to filter out files based on .gitattributes,
	// we will need to additionally check out any .gitattributes files in
	// ancestor directories.
	for _, file := range input.Files {
		cmds[2].Args = append(cmds[2].Args, file.Path)
	}
	for _, c := range cmds {
		c.Dir = tempDir
		log.Printf("Running cmd: %s", c.Args)
		if err := c.Run(); err != nil {
			log.Fatalf("Failed to run command: %v, cmd: %s", err, c.Args)
		}
	}

	// Copy files to output directory for isolation.
	// Skip over any files which couldn't be copied and don't
	// include them in the output.
	log.Printf("Copying from %q to %q.", tempDir, *outputDir)
	output := &tricium.Data_Files{
		Files: copyFiles(tempDir, *outputDir, input.Files),
	}

	// Write Tricium output FILES data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write FILES data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

// copyFiles copies over all files that we want to analyze.
//
// Files that we don't want to analyze, or that couldn't be copied,
// are filtered out; if an error occurs, we exit with a fatal error.
//
// The list of copied files is returned.
func copyFiles(inputDir, outputDir string, files []*tricium.Data_File) []*tricium.Data_File {
	var out []*tricium.Data_File
	for _, file := range files {
		src := filepath.Join(inputDir, file.Path)
		if !shouldCopy(src) {
			log.Printf("Skipping file %q", src)
			continue
		}
		log.Printf("Copying %q.", file.Path)

		dest := filepath.Join(outputDir, file.Path)
		if err := os.MkdirAll(filepath.Dir(dest), os.ModePerm); err != nil {
			log.Fatalf("Failed to create dirs for file: %v", err)
		}
		cmd := exec.Command("cp", src, dest)

		stderr, err := cmd.StderrPipe()
		if err != nil {
			log.Fatalf("Failed to read stderr: %v", err)
		}
		if err := cmd.Start(); err != nil {
			log.Fatalf("Failed to invoke command: %v", err)
		}
		slurp, _ := ioutil.ReadAll(stderr)
		if err := cmd.Wait(); err != nil {
			log.Fatalf("Command failed: %v, stderr: %s", err, slurp)
		}
		out = append(out, file)
	}
	return out
}

func shouldCopy(path string) bool {
	fileInfo, err := os.Lstat(path)
	if err != nil {
		log.Printf("Failed to stat file: %v", err)
		return false
	}
	if !fileInfo.Mode().IsRegular() {
		log.Printf("Skipping file %q with mode %s.", path, fileInfo.Mode())
		return false
	}

	if isSkipped(path) {
		log.Printf("Skipping file %q based on path.", path)
		return false
	}

	return true
}

// A set of patterns to match paths that we initially know we want to skip.
// TODO(crbug.com/904007): Remove this after .gitattributes files have been put
// in all of these places.
var (
	thirdParty         = regexp.MustCompile(`^third_party/`)
	thirdPartyBlink    = regexp.MustCompile(`^third_party/blink/`)
	webTestExpectation = regexp.MustCompile(`(web_tests|LayoutTests)/.+-expected\.(txt|png|wav)$`)
	recipeExpectation  = regexp.MustCompile(`\.expected/.*\.json$`)
	pdfiumExpectation  = regexp.MustCompile(`_expected\.txt$`)
	protoGenerated     = regexp.MustCompile(`(\.pb.go|_pb2.py)$`)
)

func isSkipped(p string) bool {
	return ((thirdParty.MatchString(p) && !thirdPartyBlink.MatchString(p)) ||
		webTestExpectation.MatchString(p) ||
		pdfiumExpectation.MatchString(p) ||
		recipeExpectation.MatchString(p) ||
		protoGenerated.MatchString(p))
}
