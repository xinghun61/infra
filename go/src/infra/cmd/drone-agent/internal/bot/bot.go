// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package bot wraps managing Swarming bots.
package bot

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"

	"go.chromium.org/luci/common/errors"
)

// Bot is the interface for interacting with a started Swarming bot.
// Wait must be called to ensure the process is waited for.
type Bot interface {
	// Wait waits for the bot process to exit.  The return value
	// on subsequent calls is undefined.
	Wait() error
	// Drain signals for the bot to drain.  Note that this requires
	// support from the bot script.  This should be handled by Swarming
	// bots by waiting for the currently running task to finish before
	// exiting.
	Drain() error
	// Terminate terminates the bot with SIGTERM.  Swarming bots handle
	// SIGTERM by aborting the currently running task and exiting.
	Terminate() error
}

type realBot struct {
	config Config
	cmd    *exec.Cmd
}

// Wait implements Bot.
func (b realBot) Wait() error {
	return b.cmd.Wait()
}

// Drain implements Bot.
func (b realBot) Drain() error {
	f, err := os.Create(b.config.drainFilePath())
	if err != nil {
		return errors.Annotate(err, "drain bot %s", b.config.BotID).Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "drain bot %s", b.config.BotID).Err()
	}
	return nil
}

// Start starts a Swarming bot.  The returned Bot object can be used
// to interact with the bot.
func Start(c Config) (Bot, error) {
	cmd := exec.Command("curl", "-sSLF", "-o", c.botZipPath(), c.botCodeURL())
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return nil, errors.Annotate(err, "start bot with %+v", c).Err()
	}
	cmd = exec.Command("python2", c.botZipPath(), "start_bot")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = c.Env
	if err := cmd.Start(); err != nil {
		return nil, errors.Annotate(err, "start bot with %+v", c).Err()
	}
	return realBot{
		config: c,
		cmd:    cmd,
	}, nil
}

// Config is the configuration needed for starting a generic Swarming bot.
type Config struct {
	// SwarmingURL is the URL of the Swarming instance.  Should be
	// a full URL without the path, e.g. https://host.example.com
	SwarmingURL string
	BotID       string
	// WorkDirectory is the Swarming bot's work directory.  The
	// caller should create this.
	WorkDirectory string
	// Env specifies the environment of the process.
	// Each entry is of the form "key=value".
	// If Env is nil, the new process uses the current process's
	// environment.
	// If Env contains duplicate environment keys, only the last
	// value in the slice for each duplicate key is used.
	Env []string
}

func (c Config) drainFilePath() string {
	return filepath.Join(c.WorkDirectory, "draining")
}

func (c Config) botZipPath() string {
	return filepath.Join(c.WorkDirectory, "swarming_bot.zip")
}

func (c Config) botCodeURL() string {
	return fmt.Sprintf("%s/bot_code?bot_id=%s", c.SwarmingURL, c.BotID)
}