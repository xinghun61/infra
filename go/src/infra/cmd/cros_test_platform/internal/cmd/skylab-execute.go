// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"

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
		c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON ExecuteRequest to read.")
		c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to JSON ExecuteResponse to write.")
		return c
	},
}

type skylabExecuteRun struct {
	subcommands.CommandRunBase
	inputPath  string
	outputPath string
}

func (c *skylabExecuteRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.validateArgs(); err != nil {
		fmt.Fprintln(a.GetErr(), err.Error())
		c.Flags.Usage()
		return exitCode(err)
	}

	_, err := c.innerRun(a, args, env)
	if err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
	}
	return exitCode(err)
}

func (c *skylabExecuteRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	if c.outputPath == "" {
		return fmt.Errorf("-output_json not specified")
	}

	return nil
}

func (c *skylabExecuteRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) (responded bool, err error) {
	request, err := readExecuteRequest(c.inputPath)
	if err != nil {
		return false, err
	}

	if err := validateRequest(request); err != nil {
		return false, err
	}

	ctx := cli.GetContext(a, c, env)

	hClient, err := httpClient(ctx, request.Config.SkylabSwarming)
	if err != nil {
		return false, err
	}

	client, err := swarming.New(ctx, hClient, request.Config.SkylabSwarming.Server)
	if err != nil {
		return false, err
	}

	response, err := c.handleRequest(ctx, a.GetErr(), request, client)
	if err != nil && response == nil {
		// Catastrophic error. There is no reasonable response to write.
		return false, err
	}

	err = writeResponse(c.outputPath, response, err)
	// This bool expression is a refactoring kludge that will soon disapppear.
	return exitCode(err) != 1, err
}

func readExecuteRequest(path string) (*steps.ExecuteRequest, error) {
	input, err := os.Open(path)
	if err != nil {
		return nil, errors.Annotate(err, "read ExecuteRequest").Err()
	}
	defer input.Close()

	request := &steps.ExecuteRequest{}
	if err := unmarshaller.Unmarshal(input, request); err != nil {
		return nil, errors.Annotate(err, "read ExecuteRequest").Err()
	}

	return request, nil
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
