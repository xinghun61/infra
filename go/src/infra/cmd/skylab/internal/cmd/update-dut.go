// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"strings"
	"text/tabwriter"
	"time"

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

// UpdateDut subcommand: update and redeploy an existing DUT.
var UpdateDut = &subcommands.Command{
	UsageLine: "update-dut [FLAGS...] HOSTNAME",
	ShortDesc: "update an existing DUT",
	LongDesc: `Update existing DUT's inventory information.

A repair task to validate DUT deployment is triggered after DUT update. See
flags to run costlier DUT preparation steps.

By default, this subcommand opens up your favourite text editor to enter the
new specs for the DUT requested. Use -new-specs-file to run non-interactively.`,
	CommandRun: func() subcommands.CommandRun {
		c := &updateDutRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.newSpecsFile, "new-specs-file", "",
			`Path to a file containing updated DUT inventory specification.
This file must contain one inventory.DeviceUnderTest JSON-encoded protobuf
message.

The JSON-encoding for protobuf messages is described at
https://developers.google.com/protocol-buffers/docs/proto3#json

The protobuf definition of inventory.DeviceUnderTest is part of
https://chromium.googlesource.com/infra/infra/+/refs/heads/master/go/src/infra/libs/skylab/inventory/device.proto`)
		c.Flags.BoolVar(&c.tail, "tail", false, "Wait for the deployment task to complete.")

		c.Flags.BoolVar(&c.installOS, "install-os", false, "Force DUT OS re-install.")
		c.Flags.BoolVar(&c.installFirmware, "install-firmware", false, "Force DUT firmware re-install.")
		c.Flags.BoolVar(&c.skipImageDownload, "skip-image-download", false, `Some DUT preparation steps require downloading OS image onto an external drive
connected to the DUT. This flag disables the download, instead using whatever
image is already downloaded onto the external drive.`)
		return c
	},
}

type updateDutRun struct {
	subcommands.CommandRunBase
	authFlags    authcli.Flags
	envFlags     envFlags
	newSpecsFile string
	tail         bool

	installOS         bool
	installFirmware   bool
	skipImageDownload bool
}

// Run implements the subcommands.CommandRun interface.
func (c *updateDutRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), err)
		return 1
	}
	return 0
}

func (c *updateDutRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(args) != 1 {
		return NewUsageError(c.Flags, "want exactly one DUT to update, got %d", len(args))
	}
	hostname := args[0]

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

	oldSpecs, err := getOldDeviceSpecs(ctx, ic, hostname)
	if err != nil {
		return err
	}
	newSpecs, err := c.getNewSpecs(a, oldSpecs)
	if err != nil {
		return err
	}

	deploymentID, err := c.triggerRedeploy(ctx, ic, oldSpecs, newSpecs)
	if err != nil {
		return err
	}
	ds, err := ic.GetDeploymentStatus(ctx, &fleet.GetDeploymentStatusRequest{
		DeploymentId: deploymentID,
	})
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

const deployStatusCheckDelay = 30 * time.Second

// tailDeployment tails an ongoing deployment, reporting status updates to the
// user.
func tailDeployment(ctx context.Context, w io.Writer, ic fleet.InventoryClient, deploymentID string, ds *fleet.GetDeploymentStatusResponse) error {
	for !isStatusFinal(ds.GetStatus()) {
		fmt.Fprintln(w, "")
		fmt.Fprintf(w, "Checking again in %s...\n", deployStatusCheckDelay)
		time.Sleep(deployStatusCheckDelay)

		var err error
		ds, err = ic.GetDeploymentStatus(ctx, &fleet.GetDeploymentStatusRequest{
			DeploymentId: deploymentID,
		})
		if err != nil {
			return errors.Annotate(err, "report deployment status").Err()
		}
		fmt.Fprintf(w, "Current status: %s", ds.GetStatus().String())
	}

	if ds.GetStatus() != fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_SUCCEEDED {
		return errors.Reason("Deployment failed. Final status: %s", ds.GetStatus().String()).Err()
	}
	fmt.Fprintln(w, "Deployment successful!")
	return nil
}

const updateDUTHelpText = "Remove the 'servo_port' attribute to auto-generate a valid servo_port."

// getNewSpecs parses the DeviceUnderTest from specsFile, or from the user.
//
// If c.newSpecsFile is provided, it is parsed.
// If c.newSpecsFile is "", getNewSpecs obtains the specs interactively from the user.
func (c *updateDutRun) getNewSpecs(a subcommands.Application, oldSpecs *inventory.DeviceUnderTest) (*inventory.DeviceUnderTest, error) {
	if c.newSpecsFile != "" {
		return parseSpecsFile(c.newSpecsFile)
	}
	return userinput.GetDeviceSpecs(oldSpecs, updateDUTHelpText, userinput.CLIPrompt(a.GetOut(), os.Stdin, true), nil)
}

// parseSpecsFile parses device specs from the user provided file.
func parseSpecsFile(specsFile string) (*inventory.DeviceUnderTest, error) {
	text, err := ioutil.ReadFile(specsFile)
	if err != nil {
		return nil, errors.Annotate(err, "parse specs file").Err()
	}
	var specs inventory.DeviceUnderTest
	err = jsonpb.Unmarshal(strings.NewReader(string(text)), &specs)
	return &specs, err
}

// triggerRedeploy kicks off a RedeployDut attempt via crosskylabadmin.
//
// This function returns the deployment task ID for the attempt.
func (c *updateDutRun) triggerRedeploy(ctx context.Context, ic fleet.InventoryClient, old, updated *inventory.DeviceUnderTest) (string, error) {
	serializedOld, err := proto.Marshal(old.GetCommon())
	if err != nil {
		return "", errors.Annotate(err, "trigger redeploy").Err()
	}
	serializedUpdated, err := proto.Marshal(updated.GetCommon())
	if err != nil {
		return "", errors.Annotate(err, "trigger redeploy").Err()
	}

	resp, err := ic.RedeployDut(ctx, &fleet.RedeployDutRequest{
		OldSpecs: serializedOld,
		NewSpecs: serializedUpdated,
		Actions: &fleet.DutDeploymentActions{
			StageImageToUsb:  c.stageImageToUsb(),
			InstallFirmware:  c.installFirmware,
			InstallTestImage: c.installOS,
		},
		Options: &fleet.DutDeploymentOptions{
			AssignServoPortIfMissing: true,
		},
	})
	if err != nil {
		return "", errors.Annotate(err, "trigger redeploy").Err()
	}
	return resp.GetDeploymentId(), nil
}

func (c *updateDutRun) stageImageToUsb() bool {
	return (c.installFirmware || c.installOS) && !c.skipImageDownload
}

// getOldDeviceSpecs gets the current device specs for hostname from
// crosskylabadmin.
func getOldDeviceSpecs(ctx context.Context, ic fleet.InventoryClient, hostname string) (*inventory.DeviceUnderTest, error) {
	oldDut, err := getDutInfo(ctx, ic, hostname)
	if err != nil {
		return nil, errors.Annotate(err, "get old specs").Err()
	}
	return oldDut, nil
}

func printDeploymentStatus(w io.Writer, deploymentID string, ds *fleet.GetDeploymentStatusResponse) (err error) {
	tw := tabwriter.NewWriter(w, 0, 2, 2, ' ', 0)
	fmt.Fprintf(tw, "Deployment ID:\t%s\n", deploymentID)
	fmt.Fprintf(tw, "Status:\t%s\n", ds.GetStatus())
	fmt.Fprintf(tw, "Inventory change URL:\t%s\n", ds.GetChangeUrl())
	fmt.Fprintf(tw, "Deploy task URL:\t%s\n", ds.GetTaskUrl())
	fmt.Fprintf(tw, "Message:\t%s\n", ds.GetMessage())
	return tw.Flush()
}

func isStatusFinal(s fleet.GetDeploymentStatusResponse_Status) bool {
	return s != fleet.GetDeploymentStatusResponse_DUT_DEPLOYMENT_STATUS_IN_PROGRESS
}
