// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"
	"log"
	"os"
	"regexp"
	"time"

	"golang.org/x/net/context"

	"infra/tools/git/state"

	"github.com/luci/luci-go/cipd/version"
	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/system/environ"
)

// versionString is the version string for this wrapper.
//
// It is displayed by augmenting Git's "version" subcommand output.
var versionString = probeVersionString()

// gitWrapperErrorReturnCode is a return code used by the Git wrapper to
// indicate a Git wrapper failure. It is intended to try and distinguish itself
// from an actual Git return code, which tend to start at 1.
const gitWrapperErrorReturnCode = 250

// gitWrapperENV is set for delegate processes both to indicate that they are
// being run within a Git wrapper and to track Git state.State.
const gitWrapperENV = "INFRA_GIT_WRAPPER"

// gitWrapperCheckENV is set to instruct delegate processes to perform a Git
// wrapper check.
//
// If a Git wrapper process observes this environment variable, it must exit
// immediately with a non-zero return code.
const gitWrapperCheckENV = "INFRA_GIT_WRAPPER_CHECK"

// gitProbe is the SystemProbe used by the main application to locate Git.
var gitProbe = SystemProbe{
	Target: "git",
}

// probeVersionString attempts to identify the version string for the current
// package.
//
// It is determined by probing the package's CIPD metadata, and will default to
// "Unknown" if the package is either not installed via CIPD or has invalid
// metadata.
func probeVersionString() string {
	info, err := version.GetStartupVersion()
	if err == nil && info.PackageName != "" && info.InstanceID != "" {
		return fmt.Sprintf("%s @ %s", info.PackageName, info.InstanceID)
	}
	return "Unknown Version"
}

func mainImpl(c context.Context, argv []string, env environ.Env, stdin io.Reader, stdout, stderr io.Writer) int {
	// If we are performing a Git wrapper check, exit immediately with a non-zero
	// return code.
	if _, ok := env.Get(gitWrapperCheckENV); ok {
		return 1
	}

	// Check if we are being passed a wrapper state.
	var st state.State
	if v, ok := env.Get(gitWrapperENV); ok {
		if err := st.FromENV(v); err != nil {
			log.Printf("WARNING: Failed to decode "+gitWrapperENV+" [%s]: %s", v, err)
		}
	}

	// Locate the system Git.
	args := argv[1:]
	self, err := os.Executable()
	switch {
	case err != nil:
		// If we can't identify our own path, we can't check our cached Git path,
		// so invalidate it.
		log.Printf("WARNING: Failed to get absolute path of self [%s]: %s", self, err)
		st.SelfPath = ""
		st.GitPath = ""

	case self != st.SelfPath:
		// The wrapper state either doesn't have a "self" path, or was built by some
		// other wrapper. Invalidate its Git state and update its "self".
		st.GitPath = ""
		st.SelfPath = self
	}

	if st.GitPath, err = gitProbe.Locate(c, self, st.GitPath, env); err != nil {
		logError(err, "failed to locate system Git")
		return gitWrapperErrorReturnCode
	}

	// Construct and execute a managed Git command.
	cmd := GitCommand{
		State:         st,
		LowSpeedLimit: 1000,
		LowSpeedTime:  5 * time.Minute,
		RetryList:     []*regexp.Regexp{DefaultGitRetryRegexp},
		Retry:         retry.Default,
		Stdin:         stdin,
		Stdout:        stdout,
		Stderr:        stderr,
	}
	rc, err := cmd.Run(c, args, env)
	if err != nil {
		logError(err, "failed to run Git")
		return gitWrapperErrorReturnCode
	}

	return rc
}

func logError(err error, reason string) {
	if err == nil {
		return
	}

	log.Printf("ERROR: %s", reason)
	rs := errors.RenderStack(err)
	if _, renderErr := rs.DumpTo(os.Stderr); renderErr != nil {
		log.Printf("ERROR: Failed to render error stack: %s", renderErr)
	}
}

func main() {
	os.Exit(mainImpl(context.Background(), os.Args, environ.System(), nil, nil, nil))
}
