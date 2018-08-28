// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package harness manages the setup and teardown of various Swarming
// bot resources for running lab tasks, like results directories and
// host info.
package harness

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"time"

	"github.com/pkg/errors"

	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

// Func is run by Run.  It is called with a Bot and the path to the
// results directory.  The Bot will have BotInfo loaded, and the
// BotInfo will be written back when the swarmingFunc returns.
type Func func(*swarming.Bot, string) error

// Run calls a function with a Swarming harness, which prepares and
// cleans up the results directory and host info.
func Run(b *swarming.Bot, f Func) (err error) {
	p, err := prepareResultsDir(b)
	if err != nil {
		return errors.Wrap(err, "prepare results dir")
	}
	defer func() {
		if err := sealResultsDir(p); err != nil {
			log.Printf("Failed to seal results directory %s", p)
			log.Print("Logs will not be offloaded to GS")
		}
	}()

	hiPath, err := prepareHostInfo(b, p)
	if err != nil {
		// This can happen if the DUT disappeared from the
		// inventory after the task was scheduled.
		return errors.Wrap(err, "prepare host info failed")
	}
	defer func() {
		if err2 := updateBotInfoFromHostInfo(hiPath, b.BotInfo); err == nil && err2 != nil {
			err = errors.Wrap(err2, "dimensions update from host info failed")
		}
	}()
	return f(b, p)
}

// prepareResultsDir creates the results dir needed for autoserv.
func prepareResultsDir(b *swarming.Bot) (string, error) {
	p := b.ResultsDir()
	if err := os.MkdirAll(p, 0755); err != nil {
		return "", err
	}
	log.Printf("Created results directory %s", p)
	return p, nil
}

const gsOffloaderMarker = ".ready_for_offload"

// sealResultsDir drops a special timestamp file in the results directory notifying
// gs_offloader to offload the directory. The results directory should not
// be touched once sealed.
func sealResultsDir(d string) error {
	ts := []byte(fmt.Sprintf("%d", time.Now().Unix()))
	tsfile := filepath.Join(d, gsOffloaderMarker)
	return ioutil.WriteFile(tsfile, ts, 0666)
}
