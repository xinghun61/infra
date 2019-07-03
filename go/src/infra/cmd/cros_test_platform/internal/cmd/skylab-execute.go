// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/cli"

	"infra/cmd/cros_test_platform/internal/execution"
)

// SkylabExecute subcommand: Run a set of enumerated tests against skylab backend.
var SkylabExecute = &subcommands.Command{
	UsageLine: "skylab-execute -input_json /path/to/input.json -output_json /path/to/output.json",
	ShortDesc: "Run a set of enumerated tests against skylab backend.",
	LongDesc: `Run a set of enumerated tests against skylab backend.

	Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &skylabExecuteRun{}
		c.addFlags()
		return c
	},
}

type skylabExecuteRun struct {
	commonExecuteRun
}

func (c *skylabExecuteRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validateArgs(); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return exitCode(err)
	}

	err := c.innerRun(a, args, env)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
	}
	return exitCode(err)
}

func (c *skylabExecuteRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	request, err := c.readRequest(c.inputPath)
	if err != nil {
		return err
	}

	if err := c.validateRequest(request); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)

	client, err := swarmingClient(ctx, request.Config.SkylabSwarming)
	if err != nil {
		return err
	}

	runner := execution.NewSkylabRunner(request.Enumeration.AutotestTests, request.RequestParams)

	response, err := c.handleRequest(ctx, runner, client)
	if err != nil && response == nil {
		// Catastrophic error. There is no reasonable response to write.
		return err
	}

	return writeResponse(c.outputPath, response, err)
}

func (c *skylabExecuteRun) validateRequest(request *steps.ExecuteRequest) error {
	if err := c.validateRequestCommon(request); err != nil {
		return err
	}

	if request.Config.SkylabSwarming == nil {
		return fmt.Errorf("nil request.config.skylab_swarming")
	}

	return nil
}
