// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the Git File Isolator analyzer.
package main

import (
	"bytes"
	"flag"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path"
	"sort"
	"strings"

	"go.chromium.org/luci/common/data/stringset"

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

	// Theoretically the max length for a command line supported by the OS
	// could theoretically be exceeded if there are many files. Despite this,
	// we generally want put all files in one command because it's faster than
	// doing one file per invocation, and simpler than batching.
	if len(input.Files) > 1000 {
		log.Printf("Warning: Many files (%d). See crbug.com/919672", len(input.Files))
	}

	// Set up the temporary directory where we'll check out the files to.
	// The temporary directory should be cleaned up before exiting.
	tempDir, err := ioutil.TempDir("", "git-file-isolator")
	if err != nil {
		log.Fatalf("Failed to setup temporary directory: %v", err)
	}
	defer func() {
		if err := os.RemoveAll(tempDir); err != nil {
			log.Fatalf("Failed to clean up temporary directory %q: %v", tempDir, err)
		}
	}()
	log.Printf("Created temporary directory %q.", tempDir)

	// Initialize the temporary repo and fetch from the given ref.
	cmds := []*exec.Cmd{
		exec.Command("git", "init"),
		exec.Command("git", "fetch", "--depth=1", "--no-tags",
			"--no-recurse-submodules", input.Repository, input.Ref),
	}
	for _, c := range cmds {
		var stderr bytes.Buffer
		c.Dir = tempDir
		c.Stderr = &stderr
		log.Printf("Running cmd: %s", c.Args)
		if err := c.Run(); err != nil {
			log.Fatalf("Failed to run command %s\n%v\nStderr: %s", c.Args, err, stderr.String())
		}
	}

	// Some files, such as generated files, should be skipped by Tricium.
	// To achieve this, the isolator filters some files out before copying.
	// Filtering the files can be done before checking out the files, because
	// filtering is based only on file path.
	files := filterSkippedFiles(input.Files, tempDir)
	if len(files) == 0 {
		log.Fatalf("Empty files list after filtering.")
	}

	// Check out the files into the temporary directory.
	c := exec.Command("git", "checkout", "FETCH_HEAD", "--")
	c.Dir = tempDir
	for _, file := range files {
		c.Args = append(c.Args, file.Path)
	}
	if err := c.Run(); err != nil {
		log.Fatalf("Failed to run command: %v, cmd: %s", err, c.Args)
	}

	// Copy files to output directory for isolation.
	log.Printf("Copying from %q to %q.", tempDir, *outputDir)
	output := &tricium.Data_Files{
		Files:         copyFiles(tempDir, *outputDir, files),
		CommitMessage: input.CommitMessage,
	}

	// Write Tricium output FILES data.
	p, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write FILES data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", p)
}

// filterSkippedFiles filters out files we don't want to analyze.
func filterSkippedFiles(files []*tricium.Data_File, dir string) []*tricium.Data_File {
	var paths []string
	for _, file := range files {
		paths = append(paths, file.Path)
	}
	checkoutGitattributes(paths, dir)
	skipped := skippedByGitattributes(paths, dir)
	var filtered []*tricium.Data_File
	for _, file := range files {
		if skipped.Has(file.Path) {
			log.Printf("Skipping file %q based on git attributes.", file.Path)
		} else {
			filtered = append(filtered, file)
		}
	}
	return filtered
}

// checkoutGitattributes checks out all relevant .gitattributes files.
func checkoutGitattributes(paths []string, dir string) {
	// We cannot directly try to check out files that may not actually be
	// there; so, we first use ls-tree to find out which files exist.
	c := exec.Command("git", "ls-tree", "--name-only", "-z", "FETCH_HEAD", "--")
	c.Dir = dir
	c.Args = append(c.Args, possibleGitattributesPaths(paths)...)
	log.Printf("Running cmd: %s", c.Args)
	out, err := c.Output()
	if err != nil {
		log.Fatalf("Failed to run command: %v, cmd: %s", err, c.Args)
	}
	existent := splitNull(string(out))
	if len(existent) == 0 {
		log.Printf("No .gitattributes files to checkout.")
		return
	}

	// After verifying which .gitattributes files exist, we can check them out.
	// This will then allow git check-attr to work.
	c = exec.Command("git", "checkout", "FETCH_HEAD", "--")
	c.Dir = dir
	c.Args = append(c.Args, existent...)
	log.Printf("Running cmd: %s", c.Args)
	out, err = c.Output()
	if err != nil {
		log.Fatalf("Failed to run command: %v, cmd: %s", err, c.Args)
	}
}

// possibleGitattributesPaths returns a sorted slice of possible .gitattributes
// file paths that could apply to the given paths in the repo.
//
// Note that all paths are assumed to be relative paths with parts separated by
// "/", since this is what is used in the tricium.Data_File type, and this is
// also what is expected in the output of git ls-tree and other git commands.
func possibleGitattributesPaths(paths []string) []string {
	var out []string
	for d := range ancestorDirectories(paths) {
		out = append(out, path.Join(d, ".gitattributes"))
	}
	sort.Strings(out)
	return out
}

// ancestorDirectories returns a set of all ancestor directories of all of the
// given paths.
//
// An ancestor directory here means means directories of the given files, and
// their parent directories, and the parent directories of those, and so on.
// The input paths are expected to be relative file paths, and the output will
// always contain empty string, which signifies "base directory".
func ancestorDirectories(paths []string) stringset.Set {
	out := stringset.Set{}
	out.Add("")
	var dir string
	for _, p := range paths {
		dir = path.Dir(p)
		for dir != "." && dir != "/" && dir != "" {
			out.Add(dir)
			dir = path.Dir(dir)
		}
	}
	return out
}

// skippedByGitattributes returns a list of files that should be skipped by
// Tricium according to .gitattributes.
//
// This method requires the .gitattributes files to be checked out. Files will
// be skipped if the attribute tricium is unset (i.e. -tricium), and will be
// included if the tricium attribute is unspecified or explicitly set.
func skippedByGitattributes(paths []string, dir string) stringset.Set {
	c := exec.Command("git", "check-attr", "-z", "tricium", "--")
	c.Args = append(c.Args, paths...)
	c.Dir = dir
	log.Printf("Running cmd: %s", c.Args)
	out, err := c.Output()
	if err != nil {
		log.Fatalf("Failed to run command: %v, cmd: %s", err, c.Args)
	}

	// The output of `git check-attr -z <attr> -- ...` is a flat null-separated
	// sequence of fields for all specified files, that looks like:
	//     path, attribute, value, path, attribute, value, ...
	skipped := stringset.Set{}
	fields := splitNull(string(out))
	if len(fields)%3 != 0 {
		log.Fatalf("Unexpected output from git check-attr: %s", out)
	}
	for i := 0; i+2 < len(fields); i += 3 {
		p, v := fields[i], fields[i+2]
		// Unsetting the attribute explicitly (with -tricium) means skip. If
		// the value is unspecified, it will be included by default. See:
		// https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tricium/docs/user-guide.md
		if v == "unset" {
			skipped.Add(p)
		}
	}
	return skipped
}

// splitNull splits a null-terminated null-separated string into parts.
func splitNull(s string) []string {
	parts := strings.Split(s, "\x00")
	return parts[:len(parts)-1]
}

// copyFiles copies files that we want to analyze to the output directory.
//
// Special files like symlinks and files that couldn't be copied
// are filtered out; if an error occurs, we exit with a fatal error.
//
// The list of successfully copied files is returned.
func copyFiles(inputDir, outputDir string, files []*tricium.Data_File) []*tricium.Data_File {
	var out []*tricium.Data_File
	for _, file := range files {
		src := path.Join(inputDir, file.Path)
		if !isRegularFile(src) {
			log.Printf("Skipping file %q", src)
			continue
		}
		log.Printf("Copying %q.", file.Path)

		dest := path.Join(outputDir, file.Path)
		if err := os.MkdirAll(path.Dir(dest), os.ModePerm); err != nil {
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

// isRegularFile checks whether the given path is a regular file,
// and not a symlink or other special file. Returns false on error.
func isRegularFile(p string) bool {
	fileInfo, err := os.Lstat(p)
	if err != nil {
		log.Printf("Failed to stat file: %v", err)
		return false
	}
	if !fileInfo.Mode().IsRegular() {
		log.Printf("File %q has mode %s.", p, fileInfo.Mode())
		return false
	}
	return true
}
