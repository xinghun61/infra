// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/gob"
	"encoding/json"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"go.chromium.org/luci/common/data/stringset"

	tricium "infra/tricium/api/v1"
)

// Paths to the required resources relative to the executable directory.
const (
	gosecPath  = "./bin/gosec"
	maxWorkers = 10
)

var (
	inputDir  = flag.String("input", "./", "Path to root of Tricium input")
	outputDir = flag.String("output", "./", "Path to root of Tricium output")
	disable   = flag.String("disable", "", "Comma-separated list of checks "+
		"or categories of checks to disable.")
	enable = flag.String("enable", "", "Comma-separated checks "+
		"or categories of checks to enable. "+
		"The enable list overrides the disable list.")
)

// Issue represents a gosec issue found during a run.
type Issue struct {
	Severity   string            `json:"severity"`
	Confidence string            `json:"confidence"`
	RuleID     string            `json:"rule_id"`
	Details    string            `json:"details"`
	File       string            `json:"file"`
	Code       string            `json:"code"`
	Line       string            `json:"line"`
	Hash       [sha256.Size]byte `json:"-"`
}

// Statistic represents a gosec run statistic.
type Statistic struct {
	Files int `json:"files"`
	Lines int `json:"lines"`
	Nosec int `json:"nosec"`
	Found int `json:"found"`
}

// GosecResult comprises the output of a gosec run in json format.
type GosecResult struct {
	Issues []Issue
	Stats  Statistic
}

// GosecRunJob specifies the required parameters to run gosec in a worker.
type GosecRunJob struct {
	File        *tricium.Data_File
	Result      *GosecResult
	Gopath      string
	PackagesDir string
}

func main() {
	os.Exit(run())
}

func run() int {
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument.")
	}
	log.Printf("Invoked with args: %v", flag.Args())

	// Getting the absolute input path is important since gosec exec is going to chdir.
	var err error
	*inputDir, err = filepath.Abs(*inputDir)
	if err != nil {
		log.Fatalf("Unable to get absolute input dir.")
	}

	// Prepare src/packages/... to simulate Gopath directory structure needed for Gosec.
	envDir, _, packagesDir, err := prepareEnv(*inputDir)
	if err != nil {
		log.Fatalf("Unable to setup gosec environment: %v", err)
	}
	defer func() {
		if err = cleanupEnv(envDir); err != nil {
			log.Fatalf("Unable to clean up gosec environment: %v", err)
		}
	}()

	log.Printf("Running gosec in parallel with %d workers.", maxWorkers)
	issues, err := runGosecParallel(maxWorkers, envDir, packagesDir)
	if err != nil {
		log.Fatal(err)
		return 1
	}

	output := &tricium.Data_Results{}
	for _, issue := range issues {
		codeLine := 0
		if codeLine, err = strconv.Atoi(issue.Line); err != nil {
			log.Printf("Unable to convert line number: %s", issue.Line)
			continue
		}

		line := int32(codeLine)
		if int(line) != codeLine {
			log.Printf("Error during int to int32 conversion of code line: %d", codeLine)
			continue
		}

		// Calculate the file path relative to the input directory.
		relpath, err := filepath.Rel(*inputDir, issue.File)
		if err != nil {
			log.Printf("Error while calculating relative path, base: %s, file: %s, err: %v",
				*inputDir, issue.File, err)
			continue
		}
		comment := &tricium.Data_Comment{
			Category:  fmt.Sprintf("Gosec/%s", issue.RuleID),
			Message:   issue.Details,
			Path:      relpath,
			StartLine: line,
			StartChar: 0,
			EndLine:   line + int32(strings.Count(issue.Code, "\n")),
			EndChar:   1,
		}
		output.Comments = append(output.Comments, comment)
	}

	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Fatalf("Failed to write analyzer results: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
	return 0
}

// prepareEnv sets up a src/packages/ directory structure to point GOPATH at it since
// Gosec requires the analysis targets to be within a valid GOPATH structure.
func prepareEnv(baseDir string) (envDir, srcDir, packages string, err error) {
	files, err := ioutil.ReadDir(baseDir)
	if err != nil {
		log.Printf("Reading basedir content: %s", baseDir)
		return "", "", "", err
	}
	envDir, err = ioutil.TempDir(baseDir, "gosec_env")
	if err != nil {
		log.Printf("Creating tempdir")
		return "", "", "", err
	}
	srcDir = filepath.Join(envDir, "src")
	err = os.Mkdir(srcDir, 0744)
	if err != nil {
		log.Printf("Creating src dir")
		return "", "", "", err
	}

	packages = filepath.Join(srcDir, "packages")
	err = os.Mkdir(packages, 0744)
	if err != nil {
		log.Printf("Creating packages dir")
		return "", "", "", err
	}
	for _, file := range files {
		orig := filepath.Join(baseDir, file.Name())
		link := filepath.Join(packages, file.Name())
		if err = os.Symlink(orig, link); err != nil {
			log.Printf("Creating symlink: %s", link)
			return "", "", "", err
		}
	}
	return envDir, srcDir, packages, nil
}

func cleanupEnv(envDir string) (result error) {
	return os.RemoveAll(envDir)
}

func getExecutableDir() string {
	ex, err := os.Executable()
	if err != nil {
		panic(err)
	}
	return filepath.Dir(ex)
}

func getGosecPath() string {
	return filepath.Join(getExecutableDir(), gosecPath)
}

func hashIssue(issue *Issue) [sha256.Size]byte {
	var b bytes.Buffer
	gob.NewEncoder(&b).Encode(issue)
	return sha256.Sum256(b.Bytes())
}

func gosecWorker(jobs chan GosecRunJob, wg *sync.WaitGroup) {
	defer func() {
		log.Printf("Worker quitting")
		wg.Done()
	}()

	for job := range jobs {
		log.Printf("Worker processing %s", job.File.Path)
		cmdName := getGosecPath()
		cmdArgs := []string{
			"-fmt", "json",
		}
		if *disable != "" {
			cmdArgs = append(cmdArgs, fmt.Sprintf("-exclude=%s", *disable))
		}
		if *enable != "" {
			cmdArgs = append(cmdArgs, fmt.Sprintf("-include=%s", *enable))
		}
		cmdArgs = append(cmdArgs, job.File.Path)
		cmd := exec.Command(cmdName, cmdArgs...)
		cmd.Env = append(os.Environ(),
			fmt.Sprintf("GOPATH=%s", job.Gopath))
		cmd.Dir = job.PackagesDir

		log.Printf("setting PWD=%s", job.PackagesDir)
		log.Printf("setting GOPATH=%s", job.Gopath)

		stdoutReader, _ := cmd.StdoutPipe()
		stderrReader, _ := cmd.StderrPipe()

		// Run the command.
		log.Printf("Running command: %s", cmd.Args)
		err := cmd.Start()
		if err != nil {
			log.Printf("Error running command %v: %v", cmd, err)
		}

		if err := json.NewDecoder(stdoutReader).Decode(job.Result); err != nil {
			log.Printf("Error decoding gosec json output: %v", err)
			buf := new(bytes.Buffer)
			buf.ReadFrom(stderrReader)
			log.Printf("gosec stderr: %s", buf.String())
			continue
		}

		// Calculate hashes.
		for c := range job.Result.Issues {
			job.Result.Issues[c].Hash = hashIssue(&job.Result.Issues[c])
		}

		// No point checking for error since gosec returns non-zero if there are findings.
		cmd.Wait()
	}
}

func min(a, b int) int {
	if a <= b {
		return a
	}
	return b
}

func postProcess(results []GosecResult, input []*tricium.Data_File, evalSymlinks bool) []Issue {
	// Create unique set of issues based on hash value.
	makeUnique := func(results []GosecResult) map[[sha256.Size]byte]Issue {
		ctr := 0
		unique := make(map[[sha256.Size]byte]Issue, 0)
		for _, result := range results {
			for _, issue := range result.Issues {
				ctr++
				if _, ok := unique[issue.Hash]; !ok {
					unique[issue.Hash] = issue
				}
			}
		}

		log.Printf("Unifying issues, before: %d, after: %d", ctr, len(unique))
		return unique
	}

	// Filter issues based on whether they occur in the given input files.
	filterFiles := func(issues map[[sha256.Size]byte]Issue, input []*tricium.Data_File) []Issue {
		ctr := 0
		filtered := make([]Issue, 0)
		abspaths := stringset.New(len(input))

		for _, file := range input {
			abspath, err := filepath.Abs(filepath.Join(*inputDir, file.Path))
			if err != nil {
				log.Printf("Unable to calculate absolute path for %s", file.Path)
			} else {
				abspaths.Add(abspath)
			}
		}

		for _, issue := range issues {
			ctr++
			if evalSymlinks {
				issue.File, _ = filepath.EvalSymlinks(issue.File)
			}
			if abspaths.Has(issue.File) {
				filtered = append(filtered, issue)
				log.Printf("Found issue in %s", issue.File)
			} else {
				log.Printf("Not found, %s, %v", issue.File, abspaths)
			}
		}

		log.Printf("Filtering relevant issues, before: %d, after: %d", ctr, len(filtered))
		return filtered
	}

	return filterFiles(makeUnique(results), input)

}

func runGosecParallel(maxWorkers int, envDir, packagesDir string) ([]Issue, error) {
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		return nil, err
	}

	log.Printf("Filtering relevant files.")
	files, err := tricium.FilterFiles(input.Files, "*.go")
	if err != nil {
		return nil, err
	}
	log.Printf("Identified %d files to process.", len(files))

	results := make([]GosecResult, len(files))
	jobs := make(chan GosecRunJob, len(files))
	var wg sync.WaitGroup

	// Create workers.
	for i := 0; i < min(maxWorkers, len(files)); i++ {
		log.Printf("Starting worker %d.", i)
		wg.Add(1)
		go gosecWorker(jobs, &wg)
	}
	log.Printf("Spawned all workers.")

	// Distribute jobs into queue.
	for c, file := range files {
		log.Printf("Distributing analysis job for file %q.", file.Path)
		jobs <- GosecRunJob{
			File:        file,
			Result:      &results[c],
			Gopath:      envDir,
			PackagesDir: packagesDir,
		}
	}
	close(jobs)

	// Wait until all workers are finished.
	wg.Wait()

	issues := postProcess(results, files, true)
	for _, issue := range issues {
		log.Printf("Issue: %v", issue)
	}

	return issues, nil
}
