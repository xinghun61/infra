// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package harness manages the setup and teardown of various Swarming
// bot resources for running lab tasks, like results directories and
// host info.
package harness

import (
	"context"
	"fmt"
	"io"
	"log"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"

	"infra/cmd/skylab_swarming_worker/internal/autotest/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/parser"
	"infra/cmd/skylab_swarming_worker/internal/swmbot"

	"infra/cmd/skylab_swarming_worker/internal/swmbot/harness/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/swmbot/harness/dutinfo"
	h_hostinfo "infra/cmd/skylab_swarming_worker/internal/swmbot/harness/hostinfo"
	"infra/cmd/skylab_swarming_worker/internal/swmbot/harness/resultsdir"
)

// Info holds information about the Swarming harness.
type Info struct {
	*swmbot.Info

	ResultsDir string
	DUTName    string
	BotInfo    *swmbot.LocalState

	fetchFreshDUTInfo bool
	labelUpdater      labelUpdater

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
func Open(ctx context.Context, b *swmbot.Info, o ...Option) (i *Info, err error) {
	i = &Info{
		Info: b,
		labelUpdater: labelUpdater{
			ctx:     ctx,
			botInfo: b,
		},
	}
	defer func(i *Info) {
		if err != nil {
			_ = i.Close()
		}
	}(i)
	for _, o := range o {
		o(i)
	}
	i.BotInfo = i.loadBotInfo(b)
	d := i.loadDUTInfo(ctx, b)
	i.DUTName = d.GetCommon().GetHostname()
	hi := i.makeHostInfo(d)
	i.addBotInfoToHostInfo(hi, i.BotInfo)
	i.ResultsDir = i.makeResultsDir(b)
	i.exposeHostInfo(hi, i.ResultsDir, i.DUTName)
	if i.err != nil {
		return nil, errors.Annotate(i.err, "open harness").Err()
	}
	return i, nil
}

// ParserArgs returns the parser.Args for the Swarming bot.
func (i *Info) ParserArgs() parser.Args {
	return parser.Args{
		ParserPath: i.ParserPath,
		ResultsDir: i.ResultsDir,
	}
}

func (i *Info) loadBotInfo(b *swmbot.Info) *swmbot.LocalState {
	if i.err != nil {
		return nil
	}
	bi, err := botinfo.Open(b)
	if err != nil {
		i.err = err
		return nil
	}
	i.closers = append(i.closers, bi)
	return &bi.LocalState
}

func (i *Info) loadDUTInfo(ctx context.Context, b *swmbot.Info) *inventory.DeviceUnderTest {
	if i.err != nil {
		return nil
	}
	var s *dutinfo.Store
	if i.fetchFreshDUTInfo {
		s, i.err = dutinfo.LoadFresh(ctx, b, i.fetchFreshDUTInfo, i.labelUpdater.update)
	} else {
		s, i.err = dutinfo.LoadCached(ctx, b, i.fetchFreshDUTInfo, i.labelUpdater.update)
	}
	if i.err != nil {
		return nil
	}
	i.closers = append(i.closers, s)
	return s.DUT
}

func (i *Info) makeHostInfo(d *inventory.DeviceUnderTest) *hostinfo.HostInfo {
	if i.err != nil {
		return nil
	}
	hip := h_hostinfo.FromDUT(d)
	i.closers = append(i.closers, hip)
	return hip.HostInfo
}

func (i *Info) addBotInfoToHostInfo(hi *hostinfo.HostInfo, bi *swmbot.LocalState) {
	if i.err != nil {
		return
	}
	hib := h_hostinfo.BorrowBotInfo(hi, bi)
	i.closers = append(i.closers, hib)
}

func (i *Info) makeResultsDir(b *swmbot.Info) string {
	if i.err != nil {
		return ""
	}
	path := b.ResultsDir()
	rdc, err := resultsdir.Open(path)
	if err != nil {
		i.err = err
		return ""
	}
	log.Printf("Created results directory %s", path)
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

// labelUpdater implements an update method that is used as a dutinfo.UpdateFunc.
type labelUpdater struct {
	ctx          context.Context
	botInfo      *swmbot.Info
	taskName     string
	updateLabels bool
}

// update is a dutinfo.UpdateFunc for updating DUT inventory labels.
// If adminServiceURL is empty, this method does nothing.
func (u labelUpdater) update(dutID string, old *inventory.SchedulableLabels, new *inventory.SchedulableLabels) error {
	if u.botInfo.AdminService == "" || !u.updateLabels {
		log.Printf("Skipping label update since no admin service was provided")
		return nil
	}
	log.Printf("Calling admin service to update labels")
	ctx, err := swmbot.WithTaskAccount(u.ctx)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	client, err := swmbot.InventoryClient(ctx, u.botInfo)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	req, err := u.makeRequest(dutID, old, new)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	resp, err := client.UpdateDutLabels(ctx, req)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	if url := resp.GetUrl(); url != "" {
		log.Printf("Updated DUT labels at %s", url)
	}
	return nil
}

func (u labelUpdater) makeRequest(dutID string, old *inventory.SchedulableLabels, new *inventory.SchedulableLabels) (*fleet.UpdateDutLabelsRequest, error) {
	nl, err := proto.Marshal(new)
	if err != nil {
		return nil, err
	}
	ol, err := proto.Marshal(old)
	if err != nil {
		return nil, err
	}
	req := fleet.UpdateDutLabelsRequest{
		DutId:     dutID,
		Labels:    nl,
		Reason:    fmt.Sprintf("%s %s", u.taskName, u.botInfo.TaskRunURL()),
		OldLabels: ol,
	}
	return &req, nil
}
