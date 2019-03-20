// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package swmbot provides interaction with the Swarming bot running
// the Skylab worker process.  This includes information about the
// Swarming bot as well as any Swarming bot local state.
package swmbot

import (
	"fmt"
	"os"
	"path/filepath"

	"infra/cmd/skylab_swarming_worker/internal/lucifer"
)

// Info contains information about the current Swarming bot.
type Info struct {
	AdminService  string
	AutotestPath  string
	DUTID         string
	Inventory     Inventory
	LuciferBinDir string
	Task          Task
}

// GetInfo returns the Info for the current Swarming bot, built from
// environment variables.
//
// Per-bot variables:
//
//   ADMIN_SERVICE: Admin service host, e.g. foo.appspot.com.
//   AUTOTEST_DIR: Path to the autotest checkout on server.
//   LUCIFER_TOOLS_DIR: Path to the lucifer installation.
//   INVENTORY_TOOLS_DIR: Path to the skylab inventory tools intallation.
//   INVENTORY_DATA_DIR: Path to the skylab_inventory data checkout.
//   SKYLAB_DUT_ID: skylab_inventory id of the DUT that belongs to this bot.
//
// Per-task variables:
//
//   SWARMING_TASK_ID: task id of the swarming task being serviced.
func GetInfo() *Info {
	return &Info{
		AdminService: os.Getenv("ADMIN_SERVICE"),
		AutotestPath: os.Getenv("AUTOTEST_DIR"),
		DUTID:        os.Getenv("SKYLAB_DUT_ID"),
		Inventory: Inventory{
			DataDir:  os.Getenv("INVENTORY_DATA_DIR"),
			ToolsDir: os.Getenv("INVENTORY_TOOLS_DIR"),
		},
		LuciferBinDir: os.Getenv("LUCIFER_TOOLS_DIR"),
		Task: Task{
			RunID: os.Getenv("SWARMING_TASK_ID"),
		},
	}
}

// Inventory describes where to find the tools and data for inventory
// information.
type Inventory struct {
	ToolsDir string
	DataDir  string
}

// Task describes the bot's current task.
type Task struct {
	RunID string
}

// LuciferConfig returns the lucifer.Config for the Swarming bot.
func (b *Info) LuciferConfig() lucifer.Config {
	return lucifer.Config{
		AutotestPath: b.AutotestPath,
		BinDir:       b.LuciferBinDir,
	}
}

// ResultsDir returns the path to the results directory used by the bot task.
func (b *Info) ResultsDir() string {
	// TODO(pprabhu): Reflect the requesting swarming server URL in the resultdir.
	// This will truly disambiguate results between different swarming servers.
	return filepath.Join(b.AutotestPath, "results", resultsSubdir(b.Task.RunID))
}

// TaskRunURL returns the URL for the current Swarming task execution.
func (b *Info) TaskRunURL() string {
	return fmt.Sprintf("https://chromeos-swarming.appspot.com/task?id=%s", b.Task.RunID)
}

// StainlessURL returns the URL to the stainless logs browser for logs offloaded
// from this task.
func (t *Task) StainlessURL() string {
	return fmt.Sprintf(
		"https://stainless.corp.google.com/browse/chromeos-autotest-results/%s/",
		resultsSubdir(t.RunID))
}

func resultsSubdir(runID string) string {
	return filepath.Join(fmt.Sprintf("swarming-%s0", runID[:len(runID)-1]), runID[len(runID)-1:])
}
