// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strings"

	"infra/libs/skylab/dutstate"

	"github.com/maruel/subcommands"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_local_state"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
)

// Serialize subcommand: Gather host info file and wrap it with DUT name.
func Serialize(authOpts auth.Options) *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "serialize -input_json /path/to/input/proto.json -output_json /path/to/output.json",
		ShortDesc: "Gather host info file and wrap it with DUT name for serialization.",
		LongDesc: `Gather host info file and wrap it with DUT name for serialization.

Get host info path and DUT identifier from the request and then read in the host info file.

Write it as a test_platform/skylab_local_state/multihost.proto JSON-pb to the file given by -output_json.
`,
		CommandRun: func() subcommands.CommandRun {
			c := &serializeRun{}

			c.authFlags.Register(&c.Flags, authOpts)

			c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON SerializeRequest to read.")
			c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to JSON MultiBotHostInfo to write.")
			return c
		},
	}
}

type serializeRun struct {
	subcommands.CommandRunBase

	authFlags authcli.Flags

	inputPath  string
	outputPath string
}

func (c *serializeRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
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

func (c *serializeRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	if c.outputPath == "" {
		return fmt.Errorf("-output_json not specified")
	}

	return nil
}

func (c *serializeRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var request skylab_local_state.SerializeRequest
	if err := readJSONPb(c.inputPath, &request); err != nil {
		return err
	}

	if err := validateSerializeRequest(&request); err != nil {
		return err
	}
	hostInfoFilePath := dutstate.HostInfoFilePath(request.ResultsDir, request.DutName)

	var hostInfo skylab_local_state.AutotestHostInfo
	if err := readJSONPb(hostInfoFilePath, &hostInfo); err != nil {
		return err
	}

	message := &skylab_local_state.MultiBotHostInfo{
		HostInfo: &hostInfo,
		DutName:  request.DutName,
	}

	return writeJSONPb(c.outputPath, message)
}

func validateSerializeRequest(request *skylab_local_state.SerializeRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	var missingArgs []string

	if request.DutName == "" {
		missingArgs = append(missingArgs, "missing DUT hostname")
	}

	if request.ResultsDir == "" {
		missingArgs = append(missingArgs, "missing results dir")
	}

	if len(missingArgs) > 0 {
		return fmt.Errorf("no %s provided", strings.Join(missingArgs, ", "))
	}

	return nil
}
