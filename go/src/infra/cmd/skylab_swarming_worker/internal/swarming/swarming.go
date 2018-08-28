// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package swarming provides tools for swarming bots.
*/
package swarming

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"infra/cmd/skylab_swarming_worker/internal/autotest"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming/botcache"
)

const (
	dataDirSymlinkEvalAttempts = 10
	dataDirSymlinkEvalSleep    = 500 * time.Millisecond
)

// Bot contains information about the current swarming bot.
// BotInfo is only populated if LoadBotInfo is called.
type Bot struct {
	AutotestPath  string
	Env           string
	DUTID         string
	Inventory     Inventory
	LuciferBinDir string
	Task          Task

	// BotInfo stores the BotInfo for LoadBotInfo and DumpBotInfo.
	BotInfo *botcache.BotInfo

	dutName string
}

/*
NewBotFromEnv returns a Bot built from the present environment variables.

Per-bot variables:

  AUTOTEST_DIR: Path to the autotest checkout on server.
  LUCIFER_TOOLS_DIR: Path to the lucifer installation.
  INVENTORY_TOOLS_DIR: Path to the skylab inventory tools intallation.
  INVENTORY_DATA_DIR: Path to the skylab_inventory data checkout.
  INVENTORY_ENVIRONMENT: skylab_inventory environment this bot is part of.
  SKYLAB_DUT_ID: skylab_inventory id of the DUT that belongs to this bot.

Per-task variables:

  SWARMING_TASK_ID: task id of the swarming task being serviced.
*/
func NewBotFromEnv() *Bot {
	return &Bot{
		AutotestPath: os.Getenv("AUTOTEST_DIR"),
		Env:          os.Getenv("INVENTORY_ENVIRONMENT"),
		DUTID:        os.Getenv("SKYLAB_DUT_ID"),
		Inventory: Inventory{
			DataDir:  os.Getenv("INVENTORY_DATA_DIR"),
			ToolsDir: os.Getenv("INVENTORY_TOOLS_DIR"),
		},
		LuciferBinDir: os.Getenv("LUCIFER_TOOLS_DIR"),
		Task: Task{
			ID: os.Getenv("SWARMING_TASK_ID"),
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
	ID string
}

// LuciferConfig returns the lucifer.Config for the swarming bot.
func (b *Bot) LuciferConfig() lucifer.Config {
	return lucifer.Config{
		AutotestPath: b.AutotestPath,
		BinDir:       b.LuciferBinDir,
	}
}

// ResultsDir returns the path to the results directory used by the bot task.
func (b *Bot) ResultsDir() string {
	// TODO(pprabhu): Reflect the requesting swarming server URL in the resultdir.
	// This will truly disambiguate results between different swarming servers.
	return filepath.Join(b.AutotestPath, "results", fmt.Sprintf("swarming-%s", b.Task.ID))
}

// LoadBotInfo loads the BotInfo for the Bot.  If the BotInfo is
// changed, DumpBotInfo should be called afterward.
func (b *Bot) LoadBotInfo() error {
	b.BotInfo = &botcache.BotInfo{}
	data, err := ioutil.ReadFile(botinfoFilePath(b))
	if err != nil {
		return err
	}
	if err := botcache.Unmarshal(data, b.BotInfo); err != nil {
		return err
	}
	return nil
}

// DumpBotInfo writes the BotInfo for the Bot for persistence.
func (b *Bot) DumpBotInfo() error {
	if b.BotInfo == nil {
		return errors.New("DumpBotInfo: BotInfo is nil")
	}
	data, err := botcache.Marshal(b.BotInfo)
	if err != nil {
		return err
	}
	return ioutil.WriteFile(botinfoFilePath(b), data, 0666)
}

// botinfoFilePath returns the path for caching dimensions for the given bot.
func botinfoFilePath(b *Bot) string {
	return filepath.Join(botcacheDirPath(b), fmt.Sprintf("%s.json", b.DUTID))
}

// botcacheDir returns the path to the cache directory for the given bot.
func botcacheDirPath(b *Bot) string {
	return filepath.Join(b.AutotestPath, "swarming_state")
}

// DUTHostInfo returns the host information for the swarming bot’s assigned DUT.
func (b *Bot) DUTHostInfo() (*autotest.HostInfo, error) {
	// TODO(pprabhu) This implementation delegates to inventory tools to convert the inventory
	// data to autotest's host_info format. Instead, support directly reading inventory here.
	ddir, err := readSymlinkTargetWithRetry(b.Inventory.DataDir)
	if err != nil {
		return nil, err
	}
	p := filepath.Join(b.Inventory.ToolsDir, "print_dut_host_info")
	cmd := exec.Command(
		p,
		"--datadir", ddir,
		"--environment", b.Env,
		"--id", b.DUTID,
	)
	r, err := cmd.Output()
	if err != nil {
		log.Printf("Failed to run command %#v", cmd)
		return nil, fmt.Errorf("Failed to obtain host info for DUT: %s", err)
	}
	return autotest.UnmarshalHostInfo(r)
}

// LoadDUTName populates DUTName for the Bot.
func (b *Bot) LoadDUTName() error {
	// TODO(pprabhu): This implementation delegates to inventory tools to
	// dump the inventory information into json, reads hostname off that.
	// Instead, support directly reading inventory here.
	ddir, err := readSymlinkTargetWithRetry(b.Inventory.DataDir)
	if err != nil {
		return err
	}
	p := filepath.Join(b.Inventory.ToolsDir, "print_dut_dimensions")
	cmd := exec.Command(
		p,
		"--datadir", ddir,
		"--environment", b.Env,
		"--id", b.DUTID,
	)
	blob, err := cmd.Output()
	if err != nil {
		return err
	}
	n, err := getDutNameFromDimensions(blob)
	if err != nil {
		return err
	}
	b.dutName = n
	return nil
}

// DUTName returns the hostname for the swarming bot’s assigned DUT.
// LoadDUTName should be called first.
func (b *Bot) DUTName() string {
	return b.dutName
}

// readSymlinkTargetWithRetry dereferences the symlink pointing to the data directory.
// This symlink can be missing for small amounts of time on the servers, but once
// the symlink has been dereferenced, the target directory is guaranteed to exist for
// ~15 minutes.
func readSymlinkTargetWithRetry(p string) (string, error) {
	var err error
	for i := 0; i <= dataDirSymlinkEvalAttempts; i++ {
		t, err := filepath.EvalSymlinks(p)
		if err == nil {
			return t, nil
		}
		time.Sleep(dataDirSymlinkEvalSleep)
	}
	log.Printf("Giving up on evaluating inventory data directory symlink due to %s", err)
	return "", fmt.Errorf("Failed to find inventory data directory for symlink %s", p)
}

// getDutNameFromDimensions extracts the DUT name from dimensions printed by the inventory tool.
func getDutNameFromDimensions(blob []byte) (string, error) {
	// We simply need the DUT name from the hostInfo.
	var d struct {
		DUTName []string `json:"dut_name"`
	}
	err := json.Unmarshal(blob, &d)
	if err != nil {
		return "", fmt.Errorf("Failed to parse DUT dimensions: %s", err)
	}
	if len(d.DUTName) == 0 {
		return "", fmt.Errorf("No DUT with hostname %s in skylab inventory", d.DUTName)
	}
	if len(d.DUTName) > 1 {
		return "", fmt.Errorf("More than one DUT with hostname %s in skylab inventory", d.DUTName)
	}
	return d.DUTName[0], nil
}
