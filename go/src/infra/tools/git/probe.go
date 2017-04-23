// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/exitcode"
	"github.com/luci/luci-go/common/system/filesystem"
)

// SystemProbe can Locate a Target executable by probing the local system PATH.
type SystemProbe struct {
	// Target is the name of the target (as seen by exec.LookPath) that we are
	// searching for.
	Target string

	// testRunCommand is a testing stub that, if not nil, will be used
	// to run the wrapper check command instead of actually running it.
	testRunCommand func(cmd *exec.Cmd) (int, error)
}

// Locate attempts to locate the system's Target by traversing the available
// PATH.
//
// self is the path of the currently-running executable. It cannot be empty, but
// may be invalid if the current executable is no longer available at that
// location.
//
// cached is the cached path, passed from wrapper to wrapper through the a
// State struct in the environment. This may be empty, if there was no cached
// path or if the cached path was invalid.
//
// env is the environment to operate with, and will not be modified during
// execution.
func (p *SystemProbe) Locate(c context.Context, self, cached string, env environ.Env) (string, error) {
	// Stat "self" to ensure that we exist. We will use this later to assert that
	// our system target is not the same file as self.
	//
	// This may fail if we have been deleted since running. If so, we will skip
	// the SameFile check.
	var selfStat os.FileInfo
	if self != "" {
		var err error
		if selfStat, err = os.Stat(self); err != nil {
			log.Printf("WARNING: Failed to stat self [%s]: %s", self, err)
		}
	}

	// If we have a cached path, check that it exists and is executable and use it
	// if it is.
	if cached != "" {
		switch cachedStat, err := os.Stat(cached); {
		case err == nil:
			// Use the cached path. First, pass it through a sanity check to ensure
			// that it is not self.
			if selfStat == nil || !os.SameFile(selfStat, cachedStat) {
				return cached, nil
			}
			log.Printf("WARNING: Cached value [%s] is the wrapper [%s]; ignoring.", cached, self)

		case os.IsNotExist(err):
			// Our cached path doesn't exist, so we will have to look for a new one.

		case err != nil:
			// We couldn't check our cached path, so we will have to look for a new
			// one. This is an unexpected error, though, so emit it.
			log.Printf("WARNING: Failed to stat cached [%s]: %s", cached, err)
		}
	}

	// Get stats on our parent directory. This may fail; if so, we'll skip the
	// SameFile check.
	var selfDirStat os.FileInfo
	if self != "" {
		selfDir := filepath.Dir(self)

		var err error
		if selfDirStat, err = os.Stat(selfDir); err != nil {
			log.Printf("WARNING: Failed to stat self directory [%s]: %s", selfDir, err)
		}
	}

	// Walk through PATH. Our goal is to find the first program named Target that
	// isn't self and doesn't identify as a wrapper.
	//
	// We determine if it is a wrapper by executing it with a State that has
	// "checkWrapper" set to true. Since we will do this repeatedly, we will
	// generate the "check enabled" environment once and reuse it for each check.
	envWithCheckEnabled := env.Clone()
	envWithCheckEnabled.Set(gitWrapperCheckENV, "1")
	envWithCheckEnabledStr := envWithCheckEnabled.Sorted()

	origPATH, _ := env.Get("PATH")
	pathParts := strings.Split(origPATH, string(os.PathListSeparator))
	checked := make(map[string]struct{}, len(pathParts))
	for _, dir := range pathParts {
		if _, ok := checked[dir]; ok {
			continue
		}
		checked[dir] = struct{}{}

		path := p.checkDir(c, dir, selfStat, selfDirStat, envWithCheckEnabledStr)
		if path != "" {
			return path, nil
		}
	}

	return "", errors.Reason("could not find target in system").
		D("target", p.Target).
		D("PATH", origPATH).
		Err()
}

// checkDir checks "checkDir" for our Target executable. It ignores
// executables whose target is the same file or shares the same parent directory
// as "self".
func (p *SystemProbe) checkDir(c context.Context, dir string, self, selfDir os.FileInfo, checkENV []string) string {
	// If we have a self directory defined, ensure that "dir" isn't the same
	// directory. If it is, we will ignore this option, since we are looking for
	// something outside of the wrapper directory.
	if selfDir != nil {
		switch checkDirStat, err := os.Stat(dir); {
		case err == nil:
			// "dir" exists; if it is the same as "selfDir", we can ignore it.
			if os.SameFile(selfDir, checkDirStat) {
				return ""
			}

		case os.IsNotExist(err):
			return ""

		default:
			log.Printf("WARNING: Failed to stat candidate directory [%s]: %s", dir, err)
			return ""
		}
	}

	t := p.lookPathWithDir(dir)
	if t == "" {
		return ""
	}

	// Make sure this file isn't the same as "self", if available.
	if self != nil {
		switch st, err := os.Stat(t); {
		case err == nil:
			if os.SameFile(self, st) {
				return ""
			}

		case os.IsNotExist(err):
			// "t" no longer exists, so we can't use it.
			return ""

		default:
			log.Printf("WARNING: Failed to stat candidate path [%s]: %s", t, err)
			return ""
		}
	}

	if err := filesystem.AbsPath(&t); err != nil {
		log.Printf("WARNING: Failed to normalize candidate path [%s]: %s", t, err)
		return ""
	}

	// Try running the candidate command and confirm that it is not a wrapper.
	switch isWrapper, err := p.checkForWrapper(c, t, checkENV); {
	case err != nil:
		log.Printf("WARNING: Failed to check if [%s] is a wrapper: %s", t, err)
		return ""

	case isWrapper:
		return ""
	}

	return t
}

// lookPathWithDir uses exec.LookPath to identify a target executable in the
// specified directory.
//
// In order to check our specific directory, we will modify the "PATH"
// environment variable, which LookPath uses, to include only that directory.
// This is done at a controlled point in the Git wrapper's execution such that
// the modification and restoration of PATH are safe.
//
// Note that tests will have to reproduce this assurance.
//
// We use LookPath over custom checking because it implements operating system
// semantics for identifying an application with a name.
func (p *SystemProbe) lookPathWithDir(dir string) string {
	// Use LookPath to identify "git".
	origPATH := os.Getenv("PATH")
	if err := os.Setenv("PATH", dir); err != nil {
		return ""
	}
	defer func() {
		// Restore our original PATH. If this fails, it is irrecoverable.
		if err := os.Setenv("PATH", origPATH); err != nil {
			panic(errors.Annotate(err).Reason("failed to restore PATH").Err())
		}
	}()

	// Scan "dir" for our target.
	t, err := exec.LookPath(p.Target)
	if err != nil {
		return ""
	}

	return t
}

// checkForWrapper executes the target path and determines if it is a wrapper.
//
// The environment that we run "path" with has the "checkWrapper" State
// flag set to true. This means that if "path" is a wrapper, it will exit
// immediately with a non-zero return code.
//
// We will run the "version" command, which should be very safe and return
// a "0". If, for whatever, reason, "path" fails returns a non-zero even if it
// isn't a wrapper, we dismiss it as unsuitable.
func (p *SystemProbe) checkForWrapper(c context.Context, path string, checkENV []string) (bool, error) {
	cmd := exec.CommandContext(c, path, "version")
	cmd.Env = checkENV

	runCommand := p.testRunCommand
	if runCommand == nil {
		// (Production)
		runCommand = func(cmd *exec.Cmd) (int, error) {
			if err := cmd.Run(); err != nil {
				if rc, ok := exitcode.Get(err); ok {
					return rc, nil
				}

				envDump := make([]string, len(checkENV))
				for i, e := range checkENV {
					envDump[i] = fmt.Sprintf("%q", e)
				}
				log.Printf("WARNING: Failed to run check command [%s] with environment: %s", path, strings.Join(envDump, " "))
				return 0, errors.Annotate(err).Reason("failed to run check command").Err()
			}
			return 0, nil
		}
	}

	// Run the command. If it returns non-zero, then "path" is considered a
	// wrapper.
	rc, err := runCommand(cmd)
	if err != nil {
		return false, err
	}
	return (rc != 0), nil
}
