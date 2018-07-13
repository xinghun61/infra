package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	tricium "infra/tricium/api/v1"
	"infra/tricium/functions/shellcheck/runner"
)

const (
	analyzerName   = "ShellCheck"
	bundledBinPath = "bin/shellcheck/shellcheck"
)

var (
	runnerLogger = log.New(os.Stderr, "shellcheck", log.LstdFlags)
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	shellCheckPath := flag.String("shellcheck_path", "", "Path to shellcheck binary")

	exclude := flag.String("exclude", "", "Exclude warnings (see shellcheck")
	shell := flag.String("shell", "", "Specify dialect (see shellcheck")

	// This is needed until/unless crbug.com/863106 is fixed.
	pathFilters := flag.String("path_filters", "", "Patterns to filter file list")

	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument")
	}

	r := &runner.Runner{
		Path:    *shellCheckPath,
		Dir:     *inputDir,
		Exclude: *exclude,
		Shell:   *shell,
		Logger:  runnerLogger,
	}

	if r.Path == "" {
		// No explicit shellcheck_bin; try to find one.
		r.Path = findShellCheckBin()
		if r.Path == "" {
			log.Fatal("Couldn't find shellcheck bin!")
		}
		// Validate that the found binary is a supported version of shellcheck.
		version, err := r.Version()
		if err != nil {
			log.Fatalf("Error checking shellcheck version: %v", err)
		}
		if !strings.HasPrefix(version, "0.") || version < "0.4" {
			log.Fatalf("Found shellcheck with unsupported version %q", version)
		}
	}

	run(r, *inputDir, *outputDir, *pathFilters)
}

func run(r *runner.Runner, inputDir, outputDir, pathFilters string) {
	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %#v", input)

	// Run shellcheck on input files.
	paths := make([]string, len(input.Files))
	for i, f := range input.Files {
		paths[i] = f.Path
	}

	// Filter input file list.
	if pathFilters != "" {
		var filteredPaths []string
		filters := strings.Split(pathFilters, ",")
		for _, p := range paths {
			for _, filter := range filters {
				matched, err := filepath.Match(filter, filepath.Base(p))
				if err != nil {
					log.Fatalf("Bad path_filters pattern %q: %v", filter, err)
				}
				if matched {
					filteredPaths = append(filteredPaths, p)
				}
			}
		}
		paths = filteredPaths
	}

	var warns []runner.Warning
	if len(paths) > 0 {
		var err error
		warns, err = r.Warnings(paths...)
		if err != nil {
			log.Fatalf("Error running shellcheck: %v", err)
		}
	} else {
		log.Printf("No files to check.")
	}

	// Convert shellcheck warnings into Tricium results.
	results := &tricium.Data_Results{}
	for _, warn := range warns {
		results.Comments = append(results.Comments, &tricium.Data_Comment{
			// e.g. "ShellCheck/SC1234"
			Category: fmt.Sprintf("%s/SC%d", analyzerName, warn.Code),
			Message:  fmt.Sprintf("%s: %s", warn.Level, warn.Message),
			Url:      warn.WikiURL(),
			Path:     warn.File,
			// shellcheck uses 1-based columns and inclusive end positions;
			// Tricium needs 0-based columns and exclusive end positions.
			StartLine: warn.Line,
			EndLine:   warn.EndLine + 1,
			StartChar: warn.Column - 1,
			EndChar:   warn.EndColumn,
		})
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, results)
}

func findShellCheckBin() string {
	// Look for bundled shellcheck next to this executable.
	ex, err := os.Executable()
	if err == nil {
		bundledPath := filepath.Join(filepath.Dir(ex), bundledBinPath)
		if path, err := exec.LookPath(bundledPath); err == nil {
			return path
		}
	}
	// Look in PATH.
	if path, err := exec.LookPath("shellcheck"); err == nil {
		return path
	}
	return ""
}
