// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package runner

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os/exec"
	"strings"
	"syscall"
)

const (
	wikiURLFmt = "https://github.com/koalaman/shellcheck/wiki/SC%d"
)

// A Runner manages shellcheck execution and output parsing.
type Runner struct {
	Path    string
	Dir     string
	Exclude string
	Enable  string
	Shell   string

	Logger interface {
		Printf(string, ...interface{})
	}
}

// Version returns the version of the shellcheck binary. It will return an
// error if `shellcheck --version` fails or has unexpected output.
func (r *Runner) Version() (string, error) {
	r.log("Executing `%s --version`", r.Path)
	output, err := exec.Command(r.Path, "--version").Output()
	if err != nil {
		return "", fmt.Errorf("`%s --version` failed: %v", r.Path, err)
	}
	r.log("Version output: %q", output)
	if !bytes.HasPrefix(bytes.TrimSpace(output), []byte("ShellCheck")) {
		return "", errors.New("unrecognized --version prefix")
	}
	idx := bytes.Index(output, []byte("version: "))
	if idx == -1 {
		return "", errors.New("unrecognized --version output")
	}
	version := output[idx+len("version: "):]
	end := bytes.IndexRune(version, '\n')
	if end != -1 {
		version = version[:end]
	}
	return string(version), nil
}

// Warnings executes shellcheck against the given paths and returns Warnings
// for any issues detected.
func (r *Runner) Warnings(paths ...string) ([]Warning, error) {
	// Build shellcheck args.
	args := []string{"--format=json1"}
	if r.Exclude != "" {
		args = append(args, fmt.Sprintf("--exclude=%s", r.Exclude))
	}
	if r.Enable != "" {
		args = append(args, fmt.Sprintf("--enable=%s", r.Enable))
	}
	if r.Shell != "" {
		args = append(args, fmt.Sprintf("--shell=%s", r.Shell))
	}
	args = append(args, paths...)

	cmd := exec.Command(r.Path, args...)
	cmd.Dir = r.Dir

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("StdoutPipe failed: %v", err)
	}

	r.log("Executing `%s %v`", cmd.Path, cmd.Args)
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("command %q Start failed: %v", r.Path, err)
	}

	var warns []Warning
	var comments Comments

	// Parse shellcheck JSON output format; defer decode error handling until
	// later to give precedence to shellcheck execution failures.
	dec := json.NewDecoder(stdout)
	nestedJSON := false
	if v, err := r.Version(); err == nil {
		nestedJSON = strings.HasPrefix(v, "0.7")
	} else {
		return nil, fmt.Errorf("Parsing version failed: %v", err)
	}
	var decodeErr error
	if nestedJSON {
		decodeErr = dec.Decode(&comments)
	} else {
		decodeErr = dec.Decode(&warns)
	}

	// Wait for shellcheck to finish.
	if err := cmd.Wait(); err != nil {
		// Get the exit status.
		exitErr, ok := err.(*exec.ExitError)
		if !ok {
			return nil, fmt.Errorf("Wait failed: %v", err)
		}
		waitStatus, ok := exitErr.Sys().(syscall.WaitStatus)
		if !ok {
			return nil, fmt.Errorf("no WaitStatus on %v", exitErr)
		}
		// Exit status 1 means "success with some issues".
		if waitStatus.ExitStatus() != 1 {
			r.log("shellcheck stderr:\n%s", exitErr.Stderr)
			return nil, fmt.Errorf("shellcheck failed: %v", err)
		}
	}

	if decodeErr != nil {
		return nil, fmt.Errorf("Decode failed: %v", decodeErr)
	}
	if nestedJSON {
		warns = comments.Comments
	}

	return warns, nil
}

func (r *Runner) log(format string, v ...interface{}) {
	if r.Logger != nil {
		r.Logger.Printf(format, v...)
	}
}

// A Warning represents an issue detected by shellcheck.
type Warning struct {
	File      string `json:"file"`
	Line      int32  `json:"line"`
	EndLine   int32  `json:"endLine"`
	Column    int32  `json:"column"`
	EndColumn int32  `json:"endColumn"`
	Level     string `json:"level"`
	Code      int32  `json:"code"`
	Message   string `json:"message"`
	// TODO(crbug.com/894543): Parse the fix field and turn it into tricium Suggestions.
}

// Comments represents a dict containing a list of Warnings emitted by shellcheck.
type Comments struct {
	Comments []Warning `json:"comments"`
}

// WikiURL returns a link to more information about this warning type.
func (w *Warning) WikiURL() string {
	return fmt.Sprintf(wikiURLFmt, w.Code)
}
