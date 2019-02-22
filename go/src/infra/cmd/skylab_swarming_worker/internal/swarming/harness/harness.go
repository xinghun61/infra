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
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/lucictx"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
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

	labelUpdater labelUpdater

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
func Open(ctx context.Context, b *swarming.Bot, o ...Option) (i *Info, err error) {
	i = &Info{
		Bot: b,
		labelUpdater: labelUpdater{
			ctx:     ctx,
			taskURL: b.TaskURL(),
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
	i.DUTName = i.getDUTName(b)
	i.BotInfo = i.loadBotInfo(b)
	d := i.loadDUTInfo(ctx, b)
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

func (i *Info) loadDUTInfo(ctx context.Context, b *swarming.Bot) *inventory.DeviceUnderTest {
	if i.err != nil {
		return nil
	}
	dis, err := dutinfo.Load(b, i.labelUpdater.update)
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

// labelUpdater implements an update method that is used as a dutinfo.UpdateFunc.
type labelUpdater struct {
	ctx          context.Context
	adminService string
	taskURL      string
	taskName     string
}

// update is a dutinfo.UpdateFunc for updating DUT inventory labels.
// If adminServiceURL is empty, this method does nothing.
func (u labelUpdater) update(dutID string, labels *inventory.SchedulableLabels) error {
	if u.adminService == "" {
		log.Printf("Skipping label update since no admin service was provided")
		return nil
	}
	log.Printf("Calling admin service to update labels")
	client, err := u.makeClient()
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	req, err := u.makeRequest(dutID, labels)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	resp, err := client.UpdateDutLabels(u.ctx, req)
	if err != nil {
		return errors.Annotate(err, "update inventory labels").Err()
	}
	if url := resp.GetUrl(); url != "" {
		log.Printf("Updated DUT labels at %s", url)
	}
	return nil
}

func (u labelUpdater) makeClient() (fleet.InventoryClient, error) {
	ctx, err := lucictx.SwitchLocalAccount(u.ctx, "task")
	if err != nil {
		return nil, err
	}
	o := auth.Options{
		Method: auth.LUCIContextMethod,
		Scopes: []string{
			auth.OAuthScopeEmail,
			"https://www.googleapis.com/auth/cloud-platform",
		},
	}
	c, err := admin.NewInventoryClient(ctx, u.adminService, o)
	if err != nil {
		return nil, err
	}
	return c, nil
}

func (u labelUpdater) makeRequest(dutID string, labels *inventory.SchedulableLabels) (*fleet.UpdateDutLabelsRequest, error) {
	d, err := proto.Marshal(labels)
	if err != nil {
		return nil, err
	}
	req := fleet.UpdateDutLabelsRequest{
		DutId:  dutID,
		Labels: d,
		Reason: fmt.Sprintf("%s %s", u.taskName, u.taskURL),
	}
	return &req, nil
}
