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

	"github.com/golang/protobuf/jsonpb"
	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/swarming"
)

var (
	unmarshaller = jsonpb.Unmarshaler{AllowUnknownFields: true}
	marshaller   = jsonpb.Marshaler{}
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
		return 1
	}

	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
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

func (c *skylabExecuteRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	request, err := readExecuteRequest(c.inputPath)
	if err != nil {
		return err
	}

	if err := validateRequest(request); err != nil {
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

	response, err := c.handleRequest(ctx, a.GetErr(), request, client)
	if err != nil {
		return err
	}

	return writeExecuteResponse(c.outputPath, response)
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

func writeExecuteResponse(path string, response *steps.ExecuteResponse) error {
	output, err := os.Create(path)
	if err != nil {
		return errors.Annotate(err, "write ExecuteResponse").Err()
	}
	defer output.Close()

	if err := marshaller.Marshal(output, response); err != nil {
		return errors.Annotate(err, "write ExecuteResponse").Err()
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
	for _, test := range req.Enumeration.Tests {
		fmt.Fprintf(output, "would have emitted task for %s", test.Name)
	}
	response := &steps.ExecuteResponse{}
	return response, nil
}
