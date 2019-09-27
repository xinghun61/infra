// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/maruel/subcommands"

	"infra/cmd/cros_test_platform/internal/execution"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/common/cli"
)

// AutotestExecute subcommand: Run a set of enumerated tests against autotest backend.
var AutotestExecute = &subcommands.Command{
	UsageLine: "autotest-execute -input_json /path/to/input.json -output_json /path/to/output.json",
	ShortDesc: "Run a set of enumerated tests against autotest backend.",
	LongDesc:  `Run a set of enumerated tests against autotest backend.`,
	CommandRun: func() subcommands.CommandRun {
		c := &autotestExecuteRun{}
		c.addFlags()
		return c
	},
}

type autotestExecuteRun struct {
	commonExecuteRun
}

func (c *autotestExecuteRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
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

func (c *autotestExecuteRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	request, err := c.readRequest(c.inputPath)
	if err != nil {
		return err
	}

	if err = c.validateRequest(request); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)
	ctx = setupLogging(ctx)

	client, err := swarmingClient(ctx, request.Config.AutotestProxy)
	if err != nil {
		return err
	}

	runner := execution.NewAutotestRunner(request.Enumeration.AutotestInvocations, request.RequestParams, request.GetConfig().GetAutotestBackend())

	maxDuration, err := ptypes.Duration(request.RequestParams.Time.MaximumDuration)
	if err != nil {
		maxDuration = 12 * time.Hour
	}

	response, err := c.handleRequest(ctx, maxDuration, runner, client, nil)
	if err != nil && response == nil {
		// Catastrophic error. There is no reasonable response to write.
		return err
	}

	return writeResponse(c.outputPath, response, err)
}

func (c *autotestExecuteRun) validateRequest(request *steps.ExecuteRequest) error {
	if err := c.validateRequestCommon(request); err != nil {
		return err
	}

	if request.Config.AutotestProxy == nil {
		return fmt.Errorf("nil request.config.autotest_proxy")
	}

	return nil
}
