// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package harness manages the setup and teardown of various Swarming
// bot resources for running lab tasks, like results directories and
// host info.
package harness

import (
	"io"
	"log"

	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/inventory"

	"infra/cmd/skylab_swarming_worker/internal/admin"
	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming"

	h_botinfo "infra/cmd/skylab_swarming_worker/internal/swarming/harness/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/dutinfo"
	h_hostinfo "infra/cmd/skylab_swarming_worker/internal/swarming/harness/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness/resultsdir"
)

// Info holds information about the Swarming harness.
type Info struct {
	*swarming.Bot

	ResultsDir string
	DUTName    string
	BotInfo    *botinfo.BotInfo

	// err tracks errors during setup to simplify error handling
	// logic.
	err error

	closers []io.Closer
}

// Close closes and flushes out the harness resources.  This is safe
// to call multiple times.
func (i *Info) Close() error {
	var errs []error
	for n := len(i.closers) - 1; n >= 0; n-- {
		if err := i.closers[n].Close(); err != nil {
			errs = append(errs, err)
		}
	}
	if len(errs) > 0 {
		return errors.Annotate(errors.MultiError(errs), "close harness").Err()
	}
	return nil
}

// Open opens and sets up the bot and task harness needed for Autotest
// jobs.  An Info struct is returned with necessary fields, which must
// be closed.
func Open(b *swarming.Bot, o ...Option) (i *Info, err error) {
	c := makeConfig(o)
	i = &Info{Bot: b}
	defer func(i *Info) {
		if err != nil {
			_ = i.Close()
		}
	}(i)
	i.DUTName = i.getDUTName(b)
	i.BotInfo = i.loadBotInfo(b)
	d := i.loadDUTInfo(b, c.adminServiceURL)
	hi := i.makeHostInfo(d)
	i.addBotInfoToHostInfo(hi, i.BotInfo)
	i.ResultsDir = i.makeResultsDir(b)
	log.Printf("Created results directory %s", i.ResultsDir)
	i.exposeHostInfo(hi, i.ResultsDir, i.DUTName)
	if i.err != nil {
		return nil, errors.Annotate(i.err, "open harness").Err()
	}
	return i, nil
}

func (i *Info) getDUTName(b *swarming.Bot) string {
	if i.err != nil {
		return ""
	}
	dutName, err := loadDUTName(b)
	i.err = err
	return dutName
}

func (i *Info) loadBotInfo(b *swarming.Bot) *botinfo.BotInfo {
	if i.err != nil {
		return nil
	}
	bi, err := h_botinfo.Open(b)
	if err != nil {
		i.err = err
		return nil
	}
	i.closers = append(i.closers, bi)
	return &bi.BotInfo
}

func (i *Info) loadDUTInfo(b *swarming.Bot, adminServiceURL string) *inventory.DeviceUnderTest {
	if i.err != nil {
		return nil
	}
	var uf dutinfo.UpdateFunc
	if adminServiceURL != "" {
		uf = func(new *inventory.DeviceUnderTest) error {
			return adminUpdateLabels(adminServiceURL, new)
		}
	}
	dis, err := dutinfo.Load(b, uf)
	if err != nil {
		i.err = err
		return nil
	}
	i.closers = append(i.closers, dis)
	return dis.DUT
}

func (i *Info) makeHostInfo(d *inventory.DeviceUnderTest) *hostinfo.HostInfo {
	if i.err != nil {
		return nil
	}
	hip := h_hostinfo.FromDUT(d)
	i.closers = append(i.closers, hip)
	return hip.HostInfo
}

func (i *Info) addBotInfoToHostInfo(hi *hostinfo.HostInfo, bi *botinfo.BotInfo) {
	if i.err != nil {
		return
	}
	hib := h_hostinfo.BorrowBotInfo(hi, bi)
	i.closers = append(i.closers, hib)
}

func (i *Info) makeResultsDir(b *swarming.Bot) string {
	if i.err != nil {
		return ""
	}
	path := b.ResultsDir()
	rdc, err := resultsdir.Open(path)
	if err != nil {
		i.err = err
		return ""
	}
	i.closers = append(i.closers, rdc)
	return path
}

func (i *Info) exposeHostInfo(hi *hostinfo.HostInfo, resultsDir string, dutName string) {
	if i.err != nil {
		return
	}
	hif, err := h_hostinfo.Expose(hi, resultsDir, dutName)
	if err != nil {
		i.err = err
		return
	}
	i.closers = append(i.closers, hif)
}

// adminUpdateLabels calls the admin service RPC service to update DUT labels.
func adminUpdateLabels(adminServiceURL string, new *inventory.DeviceUnderTest) error {
	nc := new.GetCommon()
	client, err := admin.NewInventoryClient(adminServiceURL)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	if err := admin.UpdateLabels(client, nc.GetId(), nc.GetLabels()); err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	return nil
}
