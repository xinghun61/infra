// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"
	"github.com/pkg/errors"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/phosphorus"
	"go.chromium.org/luci/common/cli"

	"infra/cros/cmd/phosphorus/internal/autotest/atutil"
)

// Prejob subcommand: Run a prejob (e.g. provision) against a DUT.
var Prejob = &subcommands.Command{
	UsageLine: "prejob -input_json /path/to/input.json",
	ShortDesc: "Run a prejob against a DUT.",
	LongDesc: `Run a prejob against a DUT.

Provision the DUT via 'autoserv --provision' if provisionable labels are set.
Otherwise, reset the DUT via 'autosev --reset'`,
	CommandRun: func() subcommands.CommandRun {
		c := &prejobRun{}
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path that contains JSON encoded test_platform.phosphorus.PrejobRequest")
		return c
	},
}

type prejobRun struct {
	commonRun
}

func (c *prejobRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validateArgs(); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}

	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		return 1
	}
	return 0
}

func (c *prejobRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var r phosphorus.PrejobRequest
	if err := readJSONPb(c.inputPath, &r); err != nil {
		return err
	}

	if err := validatePrejobRequest(r); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)

	if len(r.ProvisionableLabels) > 0 {
		return runProvision(ctx, r)
	}

	return runReset(ctx, r)
}

func validatePrejobRequest(r phosphorus.PrejobRequest) error {
	missingArgs := validateRequestConfig(r.Config)

	if r.DutHostname == "" {
		missingArgs = append(missingArgs, "DUT hostname")
	}

	if len(missingArgs) > 0 {
		return fmt.Errorf("no %s provided", strings.Join(missingArgs, ", "))
	}

	return nil
}

// runProvisions provisions a single host. It is a wrapper around
// `autoserv --provision`. It cannot modify its point arguments.
func runProvision(ctx context.Context, r phosphorus.PrejobRequest) error {
	j := getMainJob(r.Config)

	var labels []string
	for k, v := range r.ProvisionableLabels {
		labels = append(labels, k+":"+v)
	}

	subDir := fmt.Sprintf("provision_%s", r.DutHostname)
	fullPath := filepath.Join(r.Config.Task.ResultsDir, subDir)

	p := &atutil.Provision{
		Host:              r.DutHostname,
		Labels:            labels,
		LocalOnlyHostInfo: true,
		ResultsDir:        fullPath,
	}

	_, err := atutil.RunAutoserv(ctx, j, p, os.Stdout)

	if err != nil {
		return errors.Wrap(err, "run provision")
	}

	return nil
}

// runProvisions provisions a single host. It is a wrapper around
// `autoserv --reset`.
func runReset(ctx context.Context, r phosphorus.PrejobRequest) error {
	j := getMainJob(r.Config)

	subDir := fmt.Sprintf("prejob_%s", r.DutHostname)
	fullPath := filepath.Join(r.Config.Task.ResultsDir, subDir)

	a := &atutil.AdminTask{
		Host:       r.DutHostname,
		ResultsDir: fullPath,
		Type:       atutil.Reset,
	}

	_, err := atutil.RunAutoserv(ctx, j, a, os.Stdout)

	if err != nil {
		return errors.Wrap(err, "run reset")
	}

	return nil
}
