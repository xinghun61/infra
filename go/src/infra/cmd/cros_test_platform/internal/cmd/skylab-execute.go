// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"
	"net/http"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/cros_test_platform/internal/skylab"
	"infra/libs/skylab/swarming"
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
	var request steps.ExecuteRequest
	if err := readRequest(c.inputPath, &request); err != nil {
		return err
	}

	if err := validateRequest(&request); err != nil {
		return err
	}

	ctx := cli.GetContext(a, c, env)

	hClient, err := httpClient(ctx, request.Config.SkylabSwarming)
	if err != nil {
		return err
	}

	client, err := swarming.New(ctx, hClient, request.Config.SkylabSwarming.Server)
	if err != nil {
		return err
	}

	response, err := c.handleRequest(ctx, a.GetErr(), &request, client)
	if err != nil && response == nil {
		// Catastrophic error. There is no reasonable response to write.
		return err
	}

	return writeResponse(c.outputPath, response, err)
}

func validateRequest(request *steps.ExecuteRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	if request.Config == nil {
		return fmt.Errorf("nil request.Config")
	}

	if request.Config.SkylabSwarming == nil {
		return fmt.Errorf("nil request.Config.SkylabSwarming")
	}

	return nil
}

func httpClient(ctx context.Context, c *config.Config_Swarming) (*http.Client, error) {
	// TODO(akeshet): Specify ClientID and ClientSecret fields.
	options := auth.Options{
		ServiceAccountJSONPath: c.AuthJsonPath,
		Scopes:                 []string{auth.OAuthScopeEmail},
	}
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, options)
	h, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "create http client").Err()
	}
	return h, nil
}

func (c *skylabExecuteRun) handleRequest(ctx context.Context, output io.Writer, req *steps.ExecuteRequest, t *swarming.Client) (*steps.ExecuteResponse, error) {
	run := skylab.NewTaskSet(req.Enumeration.AutotestTests, req.RequestParams)
	err := run.LaunchAndWait(ctx, t)
	return run.Response(t), err
}
