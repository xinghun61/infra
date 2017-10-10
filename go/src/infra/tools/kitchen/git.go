// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bytes"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/system/environ"
)

var (
	validRevisionRe    = regexp.MustCompile("^([a-z0-9]{40}|HEAD|refs/.+)$")
	commitHashRe       = regexp.MustCompile("^[a-z0-9]{40}$")
	isRunningUnitTests = false // modified in git_test.go
)

// checkoutRepository checks out repository at revision to workdir.
// If checkoutDir is a non-empty dir and not a Git repository, return an error.
func checkoutRepository(c context.Context, env environ.Env, checkoutDir, repoURL, revision string) (string, error) {
	if !validRevisionRe.MatchString(revision) {
		return "", errors.Reason("invalid revision %q", revision).Err()
	}

	// Ensure checkoutDir either does not exist, empty or a valid Git repo.
	switch _, err := os.Stat(checkoutDir); {
	case os.IsNotExist(err):
		// Checkout dir does not exist.
		if err := ensureDir(checkoutDir); err != nil {
			return "", errors.Annotate(err, "could not create directory %q", checkoutDir).Err()
		}

	case err != nil:
		return "", errors.Annotate(err, "could not stat checkout dir %q", checkoutDir).Err()

	default:
		// checkoutDir exists. Is it a valid Git repo?
		if _, err := gitGetRevision(c, env, checkoutDir); err != nil {
			if _, ok := errors.Unwrap(err).(*exec.ExitError); !ok {
				return "", errors.Annotate(err, "git-rev-parse failed in %q", checkoutDir).Err()
			}

			// This is not a Git repo. Is it empty?
			if hasFiles, err := dirHasFiles(checkoutDir); err != nil {
				return "", errors.Annotate(err, "could not read dir %q", checkoutDir).Err()
			} else if hasFiles {
				return "", inputError("workdir %q is a non-git non-empty directory", checkoutDir)
			}
		}
	}

	// checkoutDir directory exists.

	// git-init is safe to run on an existing repo.
	if _, err := runGit(c, env, checkoutDir, "init"); err != nil {
		return "", err
	}

	var fetchRef, checkoutRef string
	if commitHashRe.MatchString(revision) {
		// Typically we cannot fetch a commit, so we assume that it is in the
		// history of the remote HEAD.
		fetchRef = "HEAD"
		checkoutRef = revision
	} else {
		fetchRef = revision
		checkoutRef = "FETCH_HEAD"
	}

	logging.Infof(c, "fetching repository %q, ref %q...", repoURL, fetchRef)
	if _, err := runGit(c, env, checkoutDir, "fetch", repoURL, fetchRef); err != nil {
		return "", errors.Annotate(err, "could not fetch").Err()
	}
	if _, err := runGit(c, env, checkoutDir, "checkout", "-q", "-f", checkoutRef); err != nil {
		return "", errors.Annotate(err, "could not checkout %q", checkoutRef).Err()
	}

	// Fetch the final Git revision.
	revision, err := gitGetRevision(c, env, checkoutDir)
	if err != nil {
		return "", errors.Annotate(err, "failed to get checkout revision").Err()
	}
	return revision, nil
}

// gitGetRevision runs "git rev-parse HEAD" in the target directory and returns
// the revision.
func gitGetRevision(c context.Context, env environ.Env, gitDir string) (string, error) {
	out, err := runGit(c, env, gitDir, "rev-parse", "HEAD")
	if err != nil {
		return "", err
	}
	return string(bytes.TrimSpace(out)), nil
}

// runGit prints the git command, runs it, redirects Stdout and Stderr and
// returns an error.
func runGit(c context.Context, env environ.Env, workDir string, args ...string) ([]byte, error) {
	// Make the tests independent of user/bot configuration.
	newArgs := args
	if isRunningUnitTests {
		newArgs = append([]string{
			"-c", "user.email=kitchen_test@example.com",
			"-c", "user.name=kitchen_test",
		}, args...)
	}

	cmd := exec.CommandContext(c, "git", newArgs...)
	if workDir != "" {
		cmd.Dir = workDir
	}
	cmd.Stderr = os.Stderr

	// Write STDOUT to both a buffer and our process' STDOUT.
	var buf bytes.Buffer
	cmd.Stdout = io.MultiWriter(os.Stdout, &buf)

	// Apply our environment. Note that PATH there doesn't affect where we look
	// for 'git', since exec.CommandContext above uses os.Getenv("PATH").
	if env.Len() > 0 {
		cmd.Env = env.Sorted()
	}

	// Log our Git command.
	renderedWorkDir := workDir
	if workDir != "" {
		if absWorkDir, err := filepath.Abs(workDir); err == nil {
			renderedWorkDir = absWorkDir
		}
	}
	logging.Infof(c, "%s$ %s\n", renderedWorkDir, strings.Join(cmd.Args, " "))

	// Run our command.
	if err := cmd.Run(); err != nil {
		return nil, errors.Annotate(err, "failed to run %q", cmd.Args).Err()
	}

	return buf.Bytes(), nil
}
