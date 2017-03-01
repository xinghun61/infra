// Copyright 2016 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"
)

var validRevisionRe = regexp.MustCompile("^([a-z0-9]{40}|HEAD|refs/.+)$")
var commitHashRe = regexp.MustCompile("^[a-z0-9]{40}$")

// checkoutRepository checks out repository at revision to workdir.
// If checkoutDir is a non-empty dir and not a Git repository, return an error.
func checkoutRepository(c context.Context, checkoutDir, repoURL, revision string) error {
	if !validRevisionRe.MatchString(revision) {
		return errors.Reason("invalid revision %(rev)q").D("rev", revision).Err()
	}

	// Ensure checkoutDir either does not exist, empty or a valid Git repo.
	switch _, err := os.Stat(checkoutDir); {
	case os.IsNotExist(err):
		// Checkout dir does not exist.
		if err := ensureDir(checkoutDir); err != nil {
			return errors.Annotate(err).Reason("could not create directory %(dir)").
				D("dir", checkoutDir).
				Err()
		}

	case err != nil:
		return errors.Annotate(err).Reason("could not stat checkout dir %(dir)q").
			D("dir", checkoutDir).
			Err()

	default:
		// checkoutDir exists. Is it a valid Git repo?
		if err := git(c, checkoutDir, "rev-parse").Run(); err != nil {
			if _, ok := err.(*exec.ExitError); !ok {
				return errors.Annotate(err).Reason("git-rev-parse failed in %(dir)q").
					D("dir", checkoutDir).
					Err()
			}
			// This is not a Git repo. Is it empty?
			if hasFiles, err := dirHasFiles(checkoutDir); err != nil {
				return errors.Annotate(err).Reason("could not read dir %(dir)q").
					D("dir", checkoutDir).
					Err()
			} else if hasFiles {
				return errors.Reason("workdir %(dir)q is a non-git non-empty directory").
					D("dir", checkoutDir).
					Err()
			}
		}
	}

	// checkoutDir directory exists.

	// git-init is safe to run on an existing repo.
	if err := runGit(c, checkoutDir, "init"); err != nil {
		return err
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
	if err := runGit(c, checkoutDir, "fetch", repoURL, fetchRef); err != nil {
		return errors.Annotate(err).Reason("could not fetch").Err()
	}
	return runGit(c, checkoutDir, "checkout", "-q", "-f", checkoutRef)
}

// git returns an *exec.Cmd for a git command, with Stderr redirected.
func git(ctx context.Context, workDir string, args ...string) *exec.Cmd {
	cmd := exec.CommandContext(ctx, "git", args...)
	if workDir != "" {
		cmd.Dir = workDir
	}
	cmd.Stderr = os.Stderr
	return cmd
}

// runGit prints the git command, runs it, redirects Stdout and Stderr and returns an error.
func runGit(c context.Context, workDir string, args ...string) error {
	cmd := git(c, workDir, args...)
	if workDir != "" {
		absWorkDir, err := filepath.Abs(workDir)
		if err != nil {
			return err
		}
		fmt.Print(absWorkDir)
	}
	fmt.Printf("$ %s\n", strings.Join(cmd.Args, " "))
	cmd.Stdout = os.Stdout
	if err := cmd.Run(); err != nil {
		return errors.Annotate(err).Reason("failed to run %(args)q").D("args", cmd.Args).Err()
	}
	return nil
}
