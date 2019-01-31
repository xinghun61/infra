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
	hbotinfo "infra/cmd/skylab_swarming_worker/internal/swarming/harness/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/dutinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/resultsdir"
)

// Info holds information about the Swarming harness.
type Info struct {
	*swarming.Bot

	ResultsDir string
	DUTName    string
	BotInfo    *botinfo.BotInfo

	botInfoStore     *hbotinfo.Store
	dutInfoStore     *dutinfo.Store
	hostInfoProxy    *hostinfo.Proxy
	hostInfoBorrower *hostinfo.Borrower
	resultsDirCloser *resultsdir.Closer
	hostInfoFile     *hostinfo.File
}

// Close closes and flushes out the harness resources.  This is safe
// to call multiple times.
func (i *Info) Close() error {
	var errs []error
	if err := i.hostInfoFile.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := i.resultsDirCloser.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := i.hostInfoBorrower.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := i.hostInfoProxy.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := i.dutInfoStore.Close(); err != nil {
		errs = append(errs, err)
	}
	if err := i.botInfoStore.Close(); err != nil {
		errs = append(errs, err)
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
			_ = i.Close()
		}
	}(i)
	dutName, err := loadDUTName(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.DUTName = dutName

	bi, err := hbotinfo.Open(b)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.botInfoStore, i.BotInfo = bi, &bi.BotInfo

	dis, err := dutinfo.Load(b, nil)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.dutInfoStore = dis

	i.hostInfoProxy = hostinfo.FromDUT(dis.DUT)
	hi := i.hostInfoProxy.HostInfo

	i.hostInfoBorrower = hostinfo.BorrowBotInfo(hi, i.BotInfo)

	i.ResultsDir = b.ResultsDir()
	rdc, err := resultsdir.Open(i.ResultsDir)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.resultsDirCloser = rdc
	log.Printf("Created results directory %s", i.ResultsDir)

	hif, err := hostinfo.Expose(hi, i.ResultsDir, i.DUTName)
	if err != nil {
		return nil, errors.Annotate(err, "open harness").Err()
	}
	i.hostInfoFile = hif
	return i, nil
}
