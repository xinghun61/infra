package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"

	tricium "infra/tricium/api/v1"
)

const (
	analyzerName   = "ShellCheck"
	bundledBinPath = "bin/shellcheck/shellcheck"
)

func findShellCheckBin() (string, error) {
	// Look for bundled shellcheck next to this executable.
	ex, err := os.Executable()
	if err != nil {
		panic(err)
	}
	bundledPath := filepath.Join(filepath.Dir(ex), bundledBinPath)
	if path, err := exec.LookPath(bundledPath); err == nil {
		return path, nil
	}

	// Look in PATH.
	if path, err := exec.LookPath("shellcheck"); err == nil {
		// Check --version output to make sure this is an acceptable binary.
		output, err := exec.Command(path, "--version").Output()
		if err != nil {
			return "", fmt.Errorf("`%s --version` failed: %v", path, err)
		}
		if !bytes.Contains(output, []byte("ShellCheck")) {
			return "", fmt.Errorf("`%s --version` bad output:\n%s", path, output)
		}
		if !bytes.Contains(output, []byte("version: 0.4.")) {
			return "", fmt.Errorf("`%s --version` bad version:\n%s", path, output)
		}
		return path, nil
	}

	return "", errors.New("shellcheck bin not found")
}

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	binPath := flag.String("shellcheck_bin", "", "Path to shellcheck binary")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatalf("Unexpected argument")
	}

	if *binPath == "" {
		var err error
		*binPath, err = findShellCheckBin()
		if err != nil {
			log.Fatalf("Couldn't find shellcheck bin: %v", err)
		}
	}

	run(*inputDir, *outputDir, *binPath)
}

func run(inputDir, outputDir, binPath string) {
	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(inputDir, input); err != nil {
		log.Fatalf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %#v", input)

	// Invoke shellcheck on the given paths.
	args := []string{"--format=json"}
	for _, f := range input.Files {
		args = append(args, f.Path)
	}

	log.Printf("Executing %s %v", binPath, args)
	scErrs, err := runShellCheck(binPath, inputDir, args)
	if err != nil {
		log.Fatalf("shellcheck failed: %v", err)
	}

	// Write Tricium RESULTS data.
	results := scErrs.toTriciumResults()
	path, err := tricium.WriteDataType(outputDir, results)
	if err != nil {
		log.Fatalf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %+v\n", path, results)
}
