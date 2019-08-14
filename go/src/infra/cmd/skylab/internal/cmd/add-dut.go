// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab/internal/site"
	"infra/cmd/skylab/internal/userinput"
	"infra/libs/skylab/inventory"
)

// AddDut subcommand: add a new DUT to inventory and prepare it for tasks.
var AddDut = &subcommands.Command{
	UsageLine: "add-dut [FLAGS...]",
	ShortDesc: "add a new DUT",
	LongDesc: `Add and a new DUT to the inventory and prepare it for tasks.

The default flags prepare the DUT by installing a stable firmware and OS image
to the DUT. These steps may be skipped via flags.
A repair task to validate DUT deployment is aleways triggered after DUT
addition.

By default, this subcommand opens up your favourite text editor to enter the
specs for the new DUT. Use -new-specs-file to run non-interactively.`,
	CommandRun: func() subcommands.CommandRun {
		c := &addDutRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.newSpecsFile, "specs-file", "",
			`Path to a file containing DUT inventory specification.
This file must contain one inventory.DeviceUnderTest JSON-encoded protobuf
message.

The JSON-encoding for protobuf messages is described at
https://developers.google.com/protocol-buffers/docs/proto3#json

The protobuf definition of inventory.DeviceUnderTest is part of
https://chromium.googlesource.com/infra/infra/+/refs/heads/master/go/src/infra/libs/skylab/inventory/device.proto`)
		c.Flags.BoolVar(&c.tail, "tail", false, "Wait for the deployment task to complete.")

		c.Flags.BoolVar(&c.skipInstallOS, "skip-install-os", false, "Do not install a stable OS image on the DUT.")
		c.Flags.BoolVar(&c.skipInstallFirmware, "skip-install-firmware", false, "Do not install a stable firmware on the DUT.")
		c.Flags.BoolVar(&c.skipImageDownload, "skip-image-download", false, `Some DUT preparation steps require downloading OS image onto an external drive
connected to the DUT. This flag disables the download, instead using whatever
image is already downloaded onto the external drive.`)
		return c
	},
}

type addDutRun struct {
	subcommands.CommandRunBase
	authFlags    authcli.Flags
	envFlags     envFlags
	newSpecsFile string
	tail         bool

	skipInstallOS       bool
	skipInstallFirmware bool
	skipImageDownload   bool
}

// Run implements the subcommands.CommandRun interface.
func (c *addDutRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *addDutRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(args) > 0 {
		return NewUsageError(c.Flags, "unexpected positional args: %s", args)
	}

	ctx := cli.GetContext(a, c, env)
	hc, err := newHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}
	e := c.envFlags.Env()
	ic := fleet.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.AdminService,
		Options: site.DefaultPRPCOptions,
	})

	specs, err := c.getSpecs(a)
	if err != nil {
		return err
	}
	setIgnoredID(specs)

	deploymentID, err := c.triggerDeploy(ctx, ic, specs)
	if err != nil {
		return err
	}
	ds, err := ic.GetDeploymentStatus(ctx, &fleet.GetDeploymentStatusRequest{DeploymentId: deploymentID})
	if err != nil {
		return err
	}
	if err := printDeploymentStatus(a.GetOut(), deploymentID, ds); err != nil {
		return err
	}

	if c.tail {
		return tailDeployment(ctx, a.GetOut(), ic, deploymentID, ds)
	}
	return nil
}

const (
	addDUTHelpText = `* All [PLACEHOLDER] values must be replaced with real values, or those fields
	must be deleted.
* By default, a valid servo_port is auto-generated that is unique to the given
	servo_host. You can force a specific servo_port to be used by supplying it as
	an attribute.`

	addDUTInitialSpecs = `{
	"common": {
		"attributes": [
			{
				"key": "servo_host",
				"value": "[PLACEHOLDER] Unqualified hostname of the servohost"
			},
			{
				"key": "servo_serial",
				"value": "[PLACEHOLDER] serial number of servo"
			}
		],
		"environment": "ENVIRONMENT_PROD",
		"hostname": "[PLACEHOLDER] Required: unqualified hostname of the host",
		"id": "[IGNORED]. Do not edit (crbug.com/950553). ID is auto-generated.",
		"labels": {
			"board": "[PLACEHOLDER] board of the DUT (roughly identifies the portage overlay the OS images come from)",
			"criticalPools": [
				"DUT_POOL_SUITES"
			],
			"model": "[PLACEHOLDER] model of the DUT (roughly identifies the DUT hardware variant)"
		}
  }
}`
	placeholderTag = "[PLACEHOLDER]"
)

// getSpecs parses the DeviceUnderTest from specsFile, or from the user.
//
// If c.specsFile is provided, it is parsed.
// If c.specsFile is "", getSpecs() obtains the specs interactively from the user.
func (c *addDutRun) getSpecs(a subcommands.Application) (*inventory.DeviceUnderTest, error) {
	if c.newSpecsFile != "" {
		return parseSpecsFile(c.newSpecsFile)
	}
	template := mustParseSpec(addDUTInitialSpecs)
	specs, err := userinput.GetDeviceSpecs(template, addDUTHelpText, userinput.CLIPrompt(a.GetOut(), os.Stdin, true), ensureNoPlaceholderValues)
	if err != nil {
		return nil, err
	}
	return specs, nil
}

// triggerDeploy kicks off a DeployDut attempt via crosskylabadmin.
//
// This function returns the deployment task ID for the attempt.
func (c *addDutRun) triggerDeploy(ctx context.Context, ic fleet.InventoryClient, specs *inventory.DeviceUnderTest) (string, error) {
	serialized, err := proto.Marshal(specs.GetCommon())
	if err != nil {
		return "", errors.Annotate(err, "trigger deploy").Err()
	}

	resp, err := ic.DeployDut(ctx, &fleet.DeployDutRequest{
		NewSpecs: [][]byte{serialized},
		Actions: &fleet.DutDeploymentActions{
			StageImageToUsb:  c.stageImageToUsb(),
			InstallFirmware:  !c.skipInstallFirmware,
			InstallTestImage: !c.skipInstallOS,
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

func (c *addDutRun) stageImageToUsb() bool {
	if c.skipInstallOS && c.skipInstallFirmware {
		return false
	}
	return !c.skipImageDownload
}

func ensureNoPlaceholderValues(specs *inventory.DeviceUnderTest) error {
	if strings.Contains(proto.MarshalTextString(specs), placeholderTag) {
		return errors.Reason(fmt.Sprintf("%s values not updated", placeholderTag)).Err()
	}
	return nil
}

func setIgnoredID(specs *inventory.DeviceUnderTest) {
	// TODO(crbug/950553) Will be ignored by crosskylabadmin, but must be included.
	v := "IGNORED"
	if specs.Common == nil {
		specs.Common = &inventory.CommonDeviceSpecs{}
	}
	specs.Common.Id = &v
}

// mustParseSpec parses the given JSON-encoded inventory.DeviceUnderTest
//
// This function panic()s on errors.
func mustParseSpec(text string) *inventory.DeviceUnderTest {
	var spec inventory.DeviceUnderTest
	if err := jsonpb.Unmarshal(strings.NewReader(text), &spec); err != nil {
		panic(fmt.Sprintf("internal error - failed to parse spec: %s", err))
	}
	return &spec
}
