// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"
	"os"
	"regexp"
	"time"

	"golang.org/x/net/context"

	"infra/tools/git/state"

	"go.chromium.org/luci/cipd/version"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/system/environ"
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

// gitWrapperTraceENV, if set and not empty, instructs the Git wrapper to emit
// trace-level logging.
//
// NOTE: This can get in the way of some processes that require output parsing.
const gitWrapperTraceENV = "INFRA_GIT_WRAPPER_TRACE"

// gitWrapperHomeENV, if set and not empty, instructs Git wrapper to substitute
// HOME with given value when calling git. Setting it to empty string removes
// HOME env var completely. Useful for overriding global git configs.
const gitWrapperHomeENV = "INFRA_GIT_WRAPPER_HOME"

// gitProbe is the SystemProbe used by the main application to locate Git.
var gitProbe = SystemProbe{
	Target:               "git",
	RelativePathOverride: []string{"bin"},
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
	// Set up our logging parameters. If we're not tracing, we will only show
	// Info and higher level logs.
	const loggingFormat = `[%{level:.1s} %{shortfile}] %{message}`
	logCfg := gologger.LoggerConfig{
		Out:    os.Stderr,
		Format: loggingFormat,
	}
	c = logCfg.Use(c)
	if v, _ := env.Get(gitWrapperTraceENV); v != "" {
		c = logging.SetLevel(c, logging.Debug)
	} else {
		c = logging.SetLevel(c, logging.Info)
	}

	// If we are performing a Git wrapper check, exit immediately with a non-zero
	// return code.
	if _, ok := env.Get(gitWrapperCheckENV); ok {
		logging.Debugf(c, "Observed check env ["+gitWrapperCheckENV+"]; exiting with non-zero code.")
		return 1
	}

	// Check if we are being passed a wrapper state.
	var st state.State
	if v, ok := env.Get(gitWrapperENV); ok {
		if err := st.FromENV(v); err != nil {
			logging.Warningf(c, "Failed to decode "+gitWrapperENV+" [%s]: %s", v, err)
		}
		logging.Debugf(c, "Loaded state from ["+gitWrapperENV+"]: %#v", st)
	}

	// Locate the system Git.
	err := gitProbe.ResolveSelf(argv[0])
	logging.Debugf(c, "Identified Git wrapper (self) path at: %s", gitProbe.self)
	switch {
	case err != nil:
		// If we can't identify our own path, we can't check our cached Git path,
		// so invalidate it.
		logging.Warningf(c, "Failed to get absolute path of self [%s]: %s", gitProbe.self, err)
		st.SelfPath = ""
		st.GitPath = ""

	case gitProbe.self != st.SelfPath:
		// The wrapper state either doesn't have a "self" path, or was built by some
		// other wrapper. Invalidate its Git state and update its "self".
		st.GitPath = ""
		st.SelfPath = gitProbe.self
	}

	if st.GitPath, err = gitProbe.Locate(c, st.GitPath, env); err != nil {
		errors.Log(c, errors.Annotate(err, "failed to locate system Git").Err())
		return gitWrapperErrorReturnCode
	}
	logging.Debugf(c, "Identified system Git at: %s", st.GitPath)

	// Setup custom HOME, if requested. This makes git lookup .gitconfig and
	// .netrc there instead of default '~'.
	if newHome, ok := env.Get(gitWrapperHomeENV); ok {
		if newHome != "" {
			env.Set("HOME", newHome)
		} else {
			env.Remove("HOME")
		}
	}

	// Construct and execute a managed Git command.
	cmd := GitCommand{
		State:         st,
		LowSpeedLimit: 1000,
		LowSpeedTime:  5 * time.Minute,
		RetryList:     []*regexp.Regexp{DefaultGitRetryRegexp},
		Retry:         gitTransientRetry,
		Stdin:         stdin,
		Stdout:        stdout,
		Stderr:        stderr,
	}
	rc, err := cmd.Run(c, argv[1:], env)
	if err != nil {
		errors.Log(c, errors.Annotate(err, "failed to run Git").Err())
		return gitWrapperErrorReturnCode
	}

	return rc
}

// gitTransientRetry returns the retry.Iterator to use when retrying Git
// transient failures.
//
// We want the retry to be fastish, but not so fast that it overwhelms or
// exacerbates the remote problem. Google Git engineers have requested a
// longer initial backoff (rather than a few milliseconds).
func gitTransientRetry() retry.Iterator {
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay:   3 * time.Second,
			Retries: 10,
		},
		Multiplier: 1.5,
	}
}

func main() {
	os.Exit(mainImpl(context.Background(), os.Args, environ.System(), nil, nil, nil))
}
