// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package harness

import (
	"fmt"
	"io/ioutil"
	"path/filepath"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

// loadBotInfo loads the BotInfo for the Bot.  If the BotInfo is
// changed, DumpBotInfo should be called afterward.
func loadBotInfo(b *swarming.Bot) (*botinfo.BotInfo, error) {
	bi := botinfo.BotInfo{}
	data, err := ioutil.ReadFile(botinfoFilePath(b))
	if err != nil {
		return nil, err
	}
	if err := botinfo.Unmarshal(data, &bi); err != nil {
		return nil, err
	}
	return &bi, nil
}

// dumpBotInfo writes the BotInfo for the Bot for persistence.
func dumpBotInfo(b *swarming.Bot, bi *botinfo.BotInfo) error {
	data, err := botinfo.Marshal(bi)
	if err != nil {
		return err
	}
	return ioutil.WriteFile(botinfoFilePath(b), data, 0666)
}

// botinfoFilePath returns the path for caching dimensions for the given bot.
func botinfoFilePath(b *swarming.Bot) string {
	return filepath.Join(botinfoDirPath(b), fmt.Sprintf("%s.json", b.DUTID))
}

// botinfoDir returns the path to the cache directory for the given bot.
func botinfoDirPath(b *swarming.Bot) string {
	return filepath.Join(b.AutotestPath, "swarming_state")
}
