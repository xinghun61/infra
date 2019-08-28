// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package bot wraps managing Swarming bots.
package bot

import (
	"fmt"
	"io"
	"net/http"
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
	if err := downloadBotCode(c); err != nil {
		return nil, errors.Annotate(err, "start bot with %+v", c).Err()
	}
	cmd := exec.Command("python2", c.botZipPath(), "start_bot")
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = append(c.env(), os.Environ()...)
	if err := cmd.Start(); err != nil {
		return nil, errors.Annotate(err, "start bot with %+v", c).Err()
	}
	return realBot{
		config: c,
		cmd:    cmd,
	}, nil
}

func downloadBotCode(c Config) error {
	f, err := os.Create(c.botZipPath())
	if err != nil {
		return errors.Annotate(err, "download bot code for %+v", c).Err()
	}
	defer f.Close()

	var h http.Client
	resp, err := h.Get(c.botCodeURL())
	if err != nil {
		return errors.Annotate(err, "download bot code for %+v", c).Err()
	}
	defer resp.Body.Close()

	if _, err := io.Copy(f, resp.Body); err != nil {
		return errors.Annotate(err, "download bot code for %+v", c).Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "download bot code for %+v", c).Err()
	}
	return nil
}

// Config is the configuration needed for starting a generic Swarming bot.
type Config struct {
	// SwarmingURL is the URL of the Swarming instance.  Should be
	// a full URL without the path, e.g. https://host.example.com
	SwarmingURL string
	BotID       string
	// WorkDirectory is the Swarming bot's work directory.
	// The caller should create this.
	// The parent directory should be writable to allow creation
	// of the drain file.
	WorkDirectory string
}

func (c Config) drainFilePath() string {
	return c.WorkDirectory + ".drain"
}

func (c Config) botZipPath() string {
	return filepath.Join(c.WorkDirectory, "swarming_bot.zip")
}

func (c Config) botCodeURL() string {
	return fmt.Sprintf("%s/bot_code?bot_id=%s", c.SwarmingURL, c.BotID)
}

func (c Config) env() []string {
	return []string{
		"SWARMING_BOT_ID=" + c.BotID,
	}
}
