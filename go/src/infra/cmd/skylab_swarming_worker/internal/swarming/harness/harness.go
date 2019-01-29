// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package harness manages the setup and teardown of various Swarming
// bot resources for running lab tasks, like results directories and
// host info.
package harness

import (
	"log"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/resultsdir"
)

// Info holds information about the Swarming harness.
type Info struct {
	*swarming.Bot
	ResultsDir       string
	resultsDirCloser *resultsdir.Closer
	DUTName          string
	BotInfo          *botinfo.BotInfo
	hostInfoPath     string
}

// Close closes and flushes out the harness resources.  This is safe
// to call multiple times.
func (i *Info) Close() error {
	var errs []error
	if err := i.resultsDirCloser.Close(); err != nil {
		errs = append(errs, err)
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

	i.ResultsDir = b.ResultsDir()
	rdc, err := resultsdir.Open(i.ResultsDir)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.resultsDirCloser = rdc
	log.Printf("Created results directory %s", i.ResultsDir)

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
