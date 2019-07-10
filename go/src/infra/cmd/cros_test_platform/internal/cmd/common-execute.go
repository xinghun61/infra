// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"fmt"
	"net/http"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/config"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/cros_test_platform/internal/execution"
	"infra/cmd/cros_test_platform/internal/execution/isolate"
	"infra/libs/skylab/swarming"
)

type commonExecuteRun struct {
	subcommands.CommandRunBase
	inputPath  string
	outputPath string
}

func (c *commonExecuteRun) addFlags() {
	c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON ExecuteRequest to read.")
	c.Flags.StringVar(&c.outputPath, "output_json", "", "Path to JSON ExecuteResponse to write.")
}

func (c *commonExecuteRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	if c.outputPath == "" {
		return fmt.Errorf("-output_json not specified")
	}

	return nil
}

func (c *commonExecuteRun) readRequest(inputPath string) (*steps.ExecuteRequest, error) {
	var request steps.ExecuteRequest
	if err := readRequest(inputPath, &request); err != nil {
		return nil, err
	}
	return &request, nil
}

func (c *commonExecuteRun) validateRequestCommon(request *steps.ExecuteRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	if request.Config == nil {
		return fmt.Errorf("nil request.config")
	}

	return nil
}

func (c *commonExecuteRun) handleRequest(ctx context.Context, runner execution.Runner, t *swarming.Client, gf isolate.GetterFactory) (*steps.ExecuteResponse, error) {
	err := runner.LaunchAndWait(ctx, t, gf)
	return runner.Response(t), err
}

func httpClient(ctx context.Context, authJSONPath string) (*http.Client, error) {
	// TODO(akeshet): Specify ClientID and ClientSecret fields.
	options := auth.Options{
		ServiceAccountJSONPath: authJSONPath,
		Scopes:                 []string{auth.OAuthScopeEmail},
	}
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, options)
	h, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "create http client").Err()
	}
	return h, nil
}

func swarmingClient(ctx context.Context, c *config.Config_Swarming) (*swarming.Client, error) {
	hClient, err := httpClient(ctx, c.AuthJsonPath)
	if err != nil {
		return nil, err
	}

	client, err := swarming.New(ctx, hClient, c.Server)
	if err != nil {
		return nil, err
	}

	return client, nil
}
