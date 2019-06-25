// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"

	"go.chromium.org/chromiumos/infra/proto/go/test_platform/steps"
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

func (c *commonExecuteRun) validateRequest(request *steps.ExecuteRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	if request.Config == nil {
		return fmt.Errorf("nil request.Config")
	}

	return nil
}
