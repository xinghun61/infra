// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package swarming provides tools for swarming bots.
*/
package swarming

import (
	"errors"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
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
	BotInfo *botinfo.BotInfo
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
	b.BotInfo = &botinfo.BotInfo{}
	data, err := ioutil.ReadFile(botinfoFilePath(b))
	if err != nil {
		return err
	}
	if err := botinfo.Unmarshal(data, b.BotInfo); err != nil {
		return err
	}
	return nil
}

// DumpBotInfo writes the BotInfo for the Bot for persistence.
func (b *Bot) DumpBotInfo() error {
	if b.BotInfo == nil {
		return errors.New("DumpBotInfo: BotInfo is nil")
	}
	data, err := botinfo.Marshal(b.BotInfo)
	if err != nil {
		return err
	}
	return ioutil.WriteFile(botinfoFilePath(b), data, 0666)
}

// botinfoFilePath returns the path for caching dimensions for the given bot.
func botinfoFilePath(b *Bot) string {
	return filepath.Join(botinfoDirPath(b), fmt.Sprintf("%s.json", b.DUTID))
}

// botinfoDir returns the path to the cache directory for the given bot.
func botinfoDirPath(b *Bot) string {
	return filepath.Join(b.AutotestPath, "swarming_state")
}
