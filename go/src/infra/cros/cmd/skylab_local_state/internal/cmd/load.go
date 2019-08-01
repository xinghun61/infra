// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/errors"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_local_state"
)

// Load subcommand: Gather DUT labels and attributes into a host info file.
var Load = &subcommands.Command{
	UsageLine: "load -input_json /path/to/input.json -output_json /path/to/output.json",
	ShortDesc: "Gather DUT labels and attributes into a host info file.",
	LongDesc: `Gather DUT labels and attributes into a host info file.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &loadRun{}
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON LoadRequest to read.")
		c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to JSON LoadResponse to write.")
		return c
	},
}

type loadRun struct {
	subcommands.CommandRunBase
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

	// TODO(zamorzaev): get host info from inventory service
	hostInfo := skylab_local_state.AutotestHostInfo{}
	writeHostInfo(request.ResultsDir, "dummy_name", hostInfo)

	response := skylab_local_state.LoadResponse{}
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

func writeHostInfo(resultsDir string, dutName string, hostInfo skylab_local_state.AutotestHostInfo) error {
	hostInfoDir := filepath.Join(resultsDir, hostInfoSubDir)
	if err := os.MkdirAll(hostInfoDir, 0755); err != nil {
		return errors.Annotate(err, "write host info").Err()
	}

	hostInfoFilePath := filepath.Join(hostInfoDir, dutName+hostInfoFileSuffix)

	writeJSONPb(hostInfoFilePath, &hostInfo)

	return nil
}
