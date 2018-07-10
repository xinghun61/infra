// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os/exec"
	"syscall"

	tricium "infra/tricium/api/v1"
)

const (
	shellCheckWikiURLFmt = "https://github.com/koalaman/shellcheck/wiki/SC%d"
)

type shellCheckError struct {
	File      string `json:"file"`
	Line      int32  `json:"line"`
	EndLine   int32  `json:"endLine"`
	Column    int32  `json:"column"`
	EndColumn int32  `json:"endColumn"`
	Level     string `json:"level"`
	Code      int32  `json:"code"`
	Message   string `json:"message"`
}

func (scErr *shellCheckError) wikiURL() string {
	return fmt.Sprintf(shellCheckWikiURLFmt, scErr.Code)
}

func (scErr *shellCheckError) toTriciumComment() *tricium.Data_Comment {
	return &tricium.Data_Comment{
		// e.g. "ShellCheck/SC1234"
		Category:  fmt.Sprintf("%s/SC%d", analyzerName, scErr.Code),
		Message:   fmt.Sprintf("%s: %s", scErr.Level, scErr.Message),
		Url:       scErr.wikiURL(),
		Path:      scErr.File,
		StartLine: scErr.Line,
		EndLine:   scErr.EndLine,
		// ShellCheck uses 1-based columns; Tricium needs 0-based.
		StartChar: scErr.Column - 1,
		EndChar:   scErr.EndColumn - 1,
	}
}

type shellCheckErrors []*shellCheckError

func (scErrs shellCheckErrors) toTriciumResults() *tricium.Data_Results {
	results := &tricium.Data_Results{}
	for _, scErr := range scErrs {
		results.Comments = append(results.Comments, scErr.toTriciumComment())
	}
	return results
}

func runShellCheck(binPath, root string, args []string) (shellCheckErrors, error) {
	cmd := exec.Command(binPath, args...)
	cmd.Dir = root
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to run %q: %v", binPath, err)
	}

	// Parse shellcheck JSON output format; defer decode error handling until
	// later to give precedence to shellcheck execution failures.
	var scErrs shellCheckErrors
	decodeErr := json.NewDecoder(stdout).Decode(&scErrs)

	// Wait for shellcheck to finish.
	if err := cmd.Wait(); err != nil {
		exitErr, ok := err.(*exec.ExitError)
		if !ok {
			return nil, fmt.Errorf("shellcheck wait failed: %v", err)
		}
		waitStatus, ok := exitErr.Sys().(syscall.WaitStatus)
		if !ok {
			log.Printf("warning: ExitError with no WaitStatus")
		}
		// Exit status 1 means "success with some issues"; we treat it as success.
		if waitStatus.ExitStatus() != 1 {
			log.Printf("shellcheck failure stderr:\n%s", exitErr.Stderr)
			return nil, fmt.Errorf("shellcheck failed: %v", err)
		}
	}

	if decodeErr != nil {
		return nil, fmt.Errorf("shellcheck output decode failed: %v", decodeErr)
	}

	return scErrs, nil
}
