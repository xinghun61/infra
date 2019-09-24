// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"github.com/maruel/subcommands"
	"github.com/pkg/errors"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/phosphorus"

	"infra/cros/cmd/phosphorus/internal/autotest"
	"infra/cros/cmd/phosphorus/internal/autotest/atutil"
)

type commonRun struct {
	subcommands.CommandRunBase

	inputPath string
}

func (c *commonRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	return nil
}

// readJSONPb reads a JSON string from inFile and unpacks it as a proto.
// Unexpected fields are ignored.
func readJSONPb(inFile string, payload proto.Message) error {
	r, err := os.Open(inFile)
	if err != nil {
		return errors.Wrap(err, "read JSON pb")
	}
	defer r.Close()

	unmarshaler := jsonpb.Unmarshaler{AllowUnknownFields: true}
	if err := unmarshaler.Unmarshal(r, payload); err != nil {
		return errors.Wrap(err, "read JSON pb")
	}
	return nil
}

// validateRequestConfig returns the list of missing required config
// arguments.
func validateRequestConfig(c *phosphorus.Config) []string {
	var missingArgs []string

	if c.GetBot().GetAutotestDir() == "" {
		missingArgs = append(missingArgs, "autotest dir")
	}

	if c.GetTask().GetResultsDir() == "" {
		missingArgs = append(missingArgs, "results dir")
	}

	return missingArgs
}

// getMainJob constructs a atutil.MainJob from a Config proto.
func getMainJob(c *phosphorus.Config) *atutil.MainJob {
	return &atutil.MainJob{
		AutotestConfig: autotest.Config{
			AutotestDir: c.GetBot().GetAutotestDir(),
		},
		ResultsDir:       c.GetTask().GetResultsDir(),
		UseLocalHostInfo: true,
	}

}
