// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/swarming"
)

// ReleaseDuts subcommand: Release a DUT previously leased via LeaseDuts.
var ReleaseDuts = &subcommands.Command{
	UsageLine: "release-duts HOST [HOST...]",
	ShortDesc: "release DUTs which are previously leased via lease-dut",
	LongDesc: `release DUTs which are previously leased via lease-dut.

This subcommand's behavior is subject to change without notice.
Do not build automation around this subcommand.`,
	CommandRun: func() subcommands.CommandRun {
		c := &releaseDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		return c
	},
}

type releaseDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
}

func (c *releaseDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *releaseDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.Flags.NArg() == 0 {
		return NewUsageError(c.Flags, "must specify at least 1 DUT")
	}
	hostnames := c.Flags.Args()

	ctx := cli.GetContext(a, c, env)
	h, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return errors.Annotate(err, "failed to create http client").Err()
	}
	e := c.envFlags.Env()
	client, err := swarming.New(ctx, h, e.SwarmingService)
	if err != nil {
		return errors.Annotate(err, "failed to create Swarming client").Err()
	}

	return cancelLeaseTasks(ctx, a.GetOut(), client, hostnames)
}

func cancelLeaseTasks(ctx context.Context, w io.Writer, client *swarming.Client, hostnames []string) error {
	errs := make(errors.MultiError, 0)
	for _, h := range hostnames {
		fmt.Fprintf(w, "Canceling lease task for host: %s\n", h)
		err := cancelLeaseTaskForHost(ctx, w, client, h)
		if err != nil {
			fmt.Fprintf(w, "Failed to cancel: %s\n", err.Error())
			errs = append(errs, err)
			continue
		}
	}
	if errs.First() != nil {
		return errs
	}
	return nil
}

func cancelLeaseTaskForHost(ctx context.Context, w io.Writer, client *swarming.Client, hostname string) error {
	ts, err := client.GetActiveLeaseTasksForHost(ctx, hostname)
	if err != nil {
		return err
	}
	if len(ts) < 1 {
		fmt.Fprintf(w, "Found no lease tasks for host %s\n", hostname)
		return nil
	}
	for _, t := range ts {
		err = client.CancelTask(ctx, t.TaskId)
		if err != nil {
			return err
		}
		fmt.Fprintf(w, "Successfully killed task %s, DUT %s is released\n", t.TaskId, hostname)
	}
	return nil
}
