// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package lucifer provides Go bindings for running lucifer.
package lucifer

import (
	"os/exec"
	"path/filepath"
	"strings"

	"infra/cmd/skylab_swarming_worker/internal/autotest/constants"

	"go.chromium.org/luci/common/flag"
)

// Config contains information needed to run Lucifer commands.
type Config struct {
	// BinDir is the directory containing Lucifer binaries.
	BinDir       string
	AutotestPath string
}

// XLevel is an enum for the available Lucifer handoff levels.  This
// is a transitory concept while the Autotest scheduler is being
// migrated to use Lucifer.
type XLevel string

// Lucifer level constants.
const (
	LuciferLevelStarting        XLevel = "STARTING"
	LuciferLevelSkylabProvision XLevel = "SKYLAB_PROVISION"
)

// TaskArgs contains the arguments shared between all Lucifer task
// types.  This can be used to facilitate share common setup code.
type TaskArgs struct {
	AbortSock  string
	GCPProject string
	ResultsDir string
	LogDogFile string
}

// TestArgs contains the arguments for creating a lucifer test
// command.  This only includes the subset of the available arguments
// that is currently needed.
type TestArgs struct {
	TaskArgs
	Hosts    []string
	TaskName string

	XTestArgs          string
	XClientTest        bool
	XJobOwner          string
	XKeyvals           map[string]string
	XLevel             XLevel
	XLocalOnlyHostInfo bool
	XPrejobTask        constants.AdminTaskType
	XProvisionLabels   []string
}

// TestCommand creates an exec.Cmd for running a lucifer test.
func TestCommand(c Config, r TestArgs) *exec.Cmd {
	p := filepath.Join(c.BinDir, "lucifer")

	args := make([]string, 0, 20)
	args = append(args, "test")
	args = append(args, "-autotestdir", c.AutotestPath)
	args = appendCommonArgs(args, r.TaskArgs)

	args = append(args, "-hosts", strings.Join(r.Hosts, ","))
	args = append(args, "-task-name", r.TaskName)

	if r.XTestArgs != "" {
		args = append(args, "-x-test-args", r.XTestArgs)
	}
	if r.XClientTest {
		args = append(args, "-x-client-test")
	} else {
		// All skylab server tests are run with SSP, but SSP may
		// be skipped within autoserv if the control file demands it.
		args = append(args, "-x-require-ssp")
	}
	args = append(args, "-x-keyvals", flag.JSONMap(&r.XKeyvals).String())
	args = append(args, "-x-job-owner", r.XJobOwner)
	args = append(args, "-x-level", string(r.XLevel))
	if r.XLocalOnlyHostInfo {
		args = append(args, "-x-local-only-host-info")
	}
	if r.XPrejobTask != constants.NoTask {
		args = append(args, "-x-prejob-task", strings.ToLower(r.XPrejobTask.String()))
	}
	if len(r.XProvisionLabels) > 0 {
		args = append(args, "-x-provision-labels", strings.Join(r.XProvisionLabels, ","))
	}

	cmd := exec.Command(p, args...)
	return cmd
}

// AdminTaskArgs contains the arguments for creating a lucifer admintask command.
type AdminTaskArgs struct {
	TaskArgs
	Host string
	Task string
	// The default values for the following are usually fine.
	GCPProject string
}

// AdminTaskCommand creates an exec.Cmd for running a lucifer admintask.
func AdminTaskCommand(c Config, a AdminTaskArgs) *exec.Cmd {
	p := filepath.Join(c.BinDir, "lucifer")
	args := make([]string, 0, 6)
	args = append(args, "admintask")
	args = append(args, "-autotestdir", c.AutotestPath)
	args = appendCommonArgs(args, a.TaskArgs)

	args = append(args, "-host", a.Host)
	args = append(args, "-task", a.Task)
	if a.GCPProject != "" {
		args = append(args, "-gcp-project", a.GCPProject)
	}

	cmd := exec.Command(p, args...)
	return cmd
}

// DeployTaskArgs contains the arguments for creating a lucifer deploytask
// command.
type DeployTaskArgs struct {
	TaskArgs
	Host    string
	Actions string
}

// DeployTaskCommand creates an exec.Cmd for running a lucifer deploytask.
func DeployTaskCommand(c Config, a DeployTaskArgs) *exec.Cmd {
	p := filepath.Join(c.BinDir, "lucifer")
	args := make([]string, 0, 6)
	args = append(args, "deploytask")
	args = append(args, "-autotestdir", c.AutotestPath)
	args = appendCommonArgs(args, a.TaskArgs)

	args = append(args, "-host", a.Host)
	if a.Actions != "" {
		args = append(args, "-actions", a.Actions)
	}
	if a.GCPProject != "" {
		args = append(args, "-gcp-project", a.GCPProject)
	}

	cmd := exec.Command(p, args...)
	return cmd
}

func appendCommonArgs(args []string, a TaskArgs) []string {
	args = append(args, "-abortsock", a.AbortSock)
	args = append(args, "-gcp-project", a.GCPProject)
	args = append(args, "-resultsdir", a.ResultsDir)
	if a.LogDogFile != "" {
		args = append(args, "-logdog-file", a.LogDogFile)
	}
	return args
}
