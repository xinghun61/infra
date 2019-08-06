// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_local_state"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
)

// Load subcommand: Gather DUT labels and attributes into a host info file.
func Load(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "load -input_json /path/to/input.json -output_json /path/to/output.json",
		ShortDesc: "Gather DUT labels and attributes into a host info file.",
		LongDesc: `Gather DUT labels and attributes into a host info file.

	Placeholder only, not yet implemented.`,
		CommandRun: func() subcommands.CommandRun {
			c := &loadRun{}

			c.authFlags.Register(&c.Flags, authOpts)

			c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON LoadRequest to read.")
			c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to JSON LoadResponse to write.")
			return c
		},
	}
}

type loadRun struct {
	subcommands.CommandRunBase

	authFlags authcli.Flags

	inputPath  string
	outputPath string
}

func (c *loadRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validateArgs(); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return 1
	}

	err := c.innerRun(a, args, env)
	if err != nil {
		fmt.Fprintf(a.GetErr(), err.Error())
		return 1
	}
	return 0
}

func (c *loadRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	if c.outputPath == "" {
		return fmt.Errorf("-output_json not specified")
	}

	return nil
}

func (c *loadRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var request skylab_local_state.LoadRequest
	if err := readJSONPb(c.inputPath, &request); err != nil {
		return err
	}

	if err := validateRequest(&request); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)

	client, err := newInventoryClient(ctx, request.Config.AdminService, &c.authFlags)
	if err != nil {
		return err
	}

	dut, err := getDutInfo(ctx, client, request.DutId)
	if err != nil {
		return err
	}

	dutName := dut.GetCommon().GetHostname()
	if dutName == "" {
		return fmt.Errorf("Empty host name")
	}

	hostInfo := hostInfoFromDutInfo(dut)

	// TODO(zamorzaev): read provisionable labels and attributes from bot state file.
	if err := writeHostInfo(request.ResultsDir, dutName, hostInfo); err != nil {
		return err
	}

	response := skylab_local_state.LoadResponse{
		DutName: dutName,
	}

	if err := writeJSONPb(c.outputPath, &response); err != nil {
		return err
	}

	return nil
}

func validateRequest(request *skylab_local_state.LoadRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	if request.Config.GetAdminService() == "" {
		return fmt.Errorf("no admin service provided")
	}

	if request.ResultsDir == "" {
		return fmt.Errorf("no results dir provided")
	}

	if request.DutId == "" {
		return fmt.Errorf("no DUT ID provided")
	}

	return nil
}

// newInventoryClient creates an admin service client.
func newInventoryClient(ctx context.Context, adminService string, authFlags *authcli.Flags) (fleet.InventoryClient, error) {
	authOpts, err := authFlags.Options()
	if err != nil {
		return nil, errors.Annotate(err, "create new inventory client").Err()
	}

	a := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)

	httpClient, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "create new inventory client").Err()
	}

	pc := prpc.Client{
		C:    httpClient,
		Host: adminService,
	}

	return fleet.NewInventoryPRPCClient(&pc), nil
}

// getDutInfo fetches the DUT inventory entry from the admin service.
func getDutInfo(ctx context.Context, client fleet.InventoryClient, dutID string) (*inventory.DeviceUnderTest, error) {
	resp, err := client.GetDutInfo(ctx, &fleet.GetDutInfoRequest{Id: dutID})
	if err != nil {
		return nil, errors.Annotate(err, "get DUT info").Err()
	}
	var dut inventory.DeviceUnderTest
	if err := proto.Unmarshal(resp.Spec, &dut); err != nil {
		return nil, errors.Annotate(err, "get DUT info").Err()
	}
	return &dut, nil
}

const currentSerializerVersion = 1

// hostInfoFromDutInfo extracts attributes and labels from an inventory
// entry and assembles them into a host info file proto.
func hostInfoFromDutInfo(dut *inventory.DeviceUnderTest) *skylab_local_state.AutotestHostInfo {
	hostInfo := skylab_local_state.AutotestHostInfo{
		Attributes:        map[string]string{},
		Labels:            labels.Convert(dut.Common.GetLabels()),
		SerializerVersion: currentSerializerVersion,
	}

	for _, attribute := range dut.Common.GetAttributes() {
		hostInfo.Attributes[attribute.GetKey()] = attribute.GetValue()
	}
	return &hostInfo
}

// writeHostInfo writes a JSON-encoded AutotestHostInfo proto to the
// DUT host info file inside the results directory.
func writeHostInfo(resultsDir string, dutName string, hostInfo *skylab_local_state.AutotestHostInfo) error {
	hostInfoDir := filepath.Join(resultsDir, hostInfoSubDir)
	if err := os.MkdirAll(hostInfoDir, 0777); err != nil {
		return errors.Annotate(err, "write host info").Err()
	}

	hostInfoFilePath := filepath.Join(hostInfoDir, dutName+hostInfoFileSuffix)

	if err := writeJSONPb(hostInfoFilePath, hostInfo); err != nil {
		return errors.Annotate(err, "write host info").Err()
	}

	return nil
}
