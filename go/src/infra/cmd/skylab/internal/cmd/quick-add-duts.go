// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"
)

// QuickAddDuts subcommand: add several new DUTs to the inventory and skip
// time-consuming steps (installing firmware, installing test image, and staging image to USB).
// This command is intended to be used only for migrating duts from autotest to skylab.
var QuickAddDuts = &subcommands.Command{
	UsageLine: "quick-add-duts [FLAGS...] DUTFILE [DUTFILE...]",
	ShortDesc: "add new DUTs skipping OS, firmware, and image download",
	LongDesc: `Add new DUTs to the inventory only. Don't perform expensive operations
(updating OS, updating firmware, downloading an image). 'quick-add-duts' should only be used
if the DUTs were successfully deployed to autotest prior to adding them to skylab.`,
	CommandRun: func() subcommands.CommandRun {
		c := &quickAddDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.BoolVar(&c.tail, "tail", false, "wait for the deployment task to complete.")
		return c
	},
}

type quickAddDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  envFlags
	tail      bool
}

// Run implements the subcommands.CommandRun interface.
func (c *quickAddDutsRun) Run(app subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(app, args, env); err != nil {
		PrintError(app.GetErr(), err)
		return 1
	}
	return 0
}

func (c *quickAddDutsRun) innerRun(app subcommands.Application, args []string, env subcommands.Env) error {
	ctx := cli.GetContext(app, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	envFlags := c.envFlags.Env()
	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    envFlags.AdminService,
		Options: site.DefaultPRPCOptions,
	})

	specs, err := getSpecs(args)
	if err != nil {
		return err
	}
	for _, spec := range specs {
		// TODO(crbug/950553): Will be ignored by crosskylabadmin, but must be included.
		setIgnoredID(spec)
	}

	deploymentID, err := triggerQuickDeploy(ctx, ic, specs)
	if err != nil {
		return err
	}
	ds, err := ic.GetDeploymentStatus(ctx, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
	if err != nil {
		return err
	}
	if err := printDeploymentStatus(app.GetOut(), deploymentID, ds); err != nil {
		return err
	}

	if c.tail {
		return tailDeployment(ctx, app.GetOut(), ic, deploymentID, ds)
	}
	return nil
}

// getSpecs parses the DeviceUnderTest from specsFile.
func getSpecs(paths []string) ([]*inventory.DeviceUnderTest, error) {
	specs := make([]*inventory.DeviceUnderTest, len(paths))
	for i, path := range paths {
		parsed, err := parseSpecsFile(path)
		if err != nil {
			return nil, err
		}
		specs[i] = parsed
	}
	return specs, nil
}

// triggerQuickDeploy kicks off a DeployDut attempt via crosskylabadmin.
//
// This function returns the deployment task ID for the attempt.
func triggerQuickDeploy(ctx context.Context, ic fleet.InventoryClient, specs []*inventory.DeviceUnderTest) (string, error) {
	newSpecs := make([][]byte, len(specs))
	for i, spec := range specs {
		serialized, err := proto.Marshal(spec.GetCommon())
		if err != nil {
			return "", errors.Annotate(err, "trigger deploy").Err()
		}
		newSpecs[i] = serialized
	}

	resp, err := ic.DeployDut(ctx, &fleet.DeployDutRequest{
		NewSpecs: newSpecs,
		Actions: &fleet.DutDeploymentActions{
			SkipDeployment: true,
		},
		Options: &fleet.DutDeploymentOptions{
			AssignServoPortIfMissing: true,
		},
	})
	if err != nil {
		return "", errors.Annotate(err, "trigger deploy").Err()
	}
	return resp.GetDeploymentId(), nil
}
