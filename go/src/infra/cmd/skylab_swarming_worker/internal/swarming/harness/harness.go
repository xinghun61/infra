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

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
)

// Info holds information about the Swarming harness.
type Info struct {
	*swarming.Bot
	ResultsDir   string
	DUTName      string
	BotInfo      *botinfo.BotInfo
	hostInfoPath string
}

// Close closes and flushes out the harness resources.  This is safe
// to call multiple times.
func (i *Info) Close() error {
	var errs []error
	if i.ResultsDir != "" {
		if err := sealResultsDir(i.ResultsDir); err != nil {
			errs = append(errs, err)
		}
		i.ResultsDir = ""
	}
	if i.hostInfoPath != "" && i.BotInfo != nil {
		if err := updateBotInfoFromHostInfo(i.hostInfoPath, i.BotInfo); err != nil {
			errs = append(errs, err)
		}
		i.hostInfoPath = ""
	}
	if i.BotInfo != nil {
		if err := dumpBotInfo(i.Bot, i.BotInfo); err == nil {
			errs = append(errs, err)
		}
		i.BotInfo = nil
	}
	if len(errs) > 0 {
		return errors.Annotate(errors.MultiError(errs), "close harness").Err()
	}
	return nil
}

// Open opens and sets up the bot and task harness needed for Autotest
// jobs.  An Info struct is returned with necessary fields, which must
// be closed.
func Open(b *swarming.Bot) (i *Info, err error) {
	i = &Info{Bot: b}
	defer func(i *Info) {
		if err != nil {
			i.Close()
		}
	}(i)
	dutName, err := loadDUTName(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.DUTName = dutName

	bi, err := loadBotInfo(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.BotInfo = bi

	rd, err := prepareResultsDir(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.ResultsDir = rd
	log.Printf("Created results directory %s", rd)

	hi, err := loadDUTHostInfo(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	addBotInfoToHostInfo(hi, i.BotInfo)
	hiPath, err := dumpHostInfo(i.DUTName, i.ResultsDir, hi)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.hostInfoPath = hiPath
	return i, nil
}

// prepareResultsDir creates the results dir needed for autoserv.
func prepareResultsDir(b *swarming.Bot) (string, error) {
	p := b.ResultsDir()
	if err := os.MkdirAll(p, 0755); err != nil {
		return "", errors.Annotate(err, "prepare results dir %s", p).Err()
	}
	return p, nil
}

const gsOffloaderMarker = ".ready_for_offload"

// sealResultsDir drops a special timestamp file in the results directory notifying
// gs_offloader to offload the directory. The results directory should not
// be touched once sealed.
func sealResultsDir(d string) error {
	ts := []byte(fmt.Sprintf("%d", time.Now().Unix()))
	tsfile := filepath.Join(d, gsOffloaderMarker)
	if err := ioutil.WriteFile(tsfile, ts, 0666); err != nil {
		return errors.Annotate(err, "seal results dir %s", d).Err()
	}
	return nil
}
