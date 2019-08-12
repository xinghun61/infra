// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strings"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/errors"

	"go.chromium.org/chromiumos/infra/proto/go/lab_platform"
	"go.chromium.org/chromiumos/infra/proto/go/test_platform/skylab_local_state"
	"infra/libs/skylab/dutstate"
)

// Save subcommand: Update the bot state json file.
func Save() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "save -input_json /path/to/input.json",
		ShortDesc: "Update the DUT state json file.",
		LongDesc: `Update the DUT state json file.

(Re)Create the DUT state cache file using the state string from the input file
and provisionable labels and attributes from the host info file.
`,
		CommandRun: func() subcommands.CommandRun {
			c := &saveRun{}

			c.Flags.StringVar(&c.inputPath, "input_json", "", "Path to JSON SaveRequest to read.")
			return c
		},
	}
}

type saveRun struct {
	subcommands.CommandRunBase

	inputPath string
}

func (c *saveRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
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

func (c *saveRun) validateArgs() error {
	if c.inputPath == "" {
		return fmt.Errorf("-input_json not specified")
	}

	return nil
}

func (c *saveRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	var request skylab_local_state.SaveRequest
	if err := readJSONPb(c.inputPath, &request); err != nil {
		return err
	}

	if err := validateSaveRequest(&request); err != nil {
		return err
	}

	i, err := getHostInfo(request.ResultsDir, request.DutName)

	if err != nil {
		return err
	}

	s := &lab_platform.DutState{
		State: request.DutState,
	}

	updateDutStateFromHostInfo(s, i)

	writeDutState(request.Config.AutotestDir, request.DutId, s)

	return nil
}

func validateSaveRequest(request *skylab_local_state.SaveRequest) error {
	if request == nil {
		return fmt.Errorf("nil request")
	}

	var missingArgs []string

	if request.Config.GetAutotestDir() == "" {
		missingArgs = append(missingArgs, "autotest dir")
	}

	if request.ResultsDir == "" {
		missingArgs = append(missingArgs, "results dir")
	}

	if request.DutName == "" {
		missingArgs = append(missingArgs, "DUT hostname")
	}

	if request.DutId == "" {
		missingArgs = append(missingArgs, "DUT ID")
	}

	if request.DutState == "" {
		missingArgs = append(missingArgs, "DUT state")
	}

	if len(missingArgs) > 0 {
		return fmt.Errorf("no %s provided", strings.Join(missingArgs, ", "))
	}

	return nil
}

// getHostInfo reads the host info from the store file.
func getHostInfo(resultsDir string, dutName string) (*skylab_local_state.AutotestHostInfo, error) {
	p := dutstate.HostInfoFilePath(resultsDir, dutName)
	i := skylab_local_state.AutotestHostInfo{}

	if err := readJSONPb(p, &i); err != nil {
		return nil, errors.Annotate(err, "get host info").Err()
	}

	return &i, nil
}

// updateDutStateFromHostInfo populates provisionable labels and provisionable
// attributes inside the DUT state with whitelisted labels and attributes from
// the host info.
func updateDutStateFromHostInfo(s *lab_platform.DutState, i *skylab_local_state.AutotestHostInfo) {
	// Should never happen.
	if s == nil {
		return
	}

	pl := dutstate.ProvisionableLabelSet()
	s.ProvisionableLabels = map[string]string{}

	for _, label := range i.GetLabels() {
		parts := strings.SplitN(label, ":", 2)
		if len(parts) != 2 {
			continue
		}
		if pl.Has(parts[0]) {
			s.ProvisionableLabels[parts[0]] = parts[1]
		}
	}

	pa := dutstate.ProvisionableAttributeSet()
	s.ProvisionableAttributes = map[string]string{}

	for attribute, value := range i.GetAttributes() {
		if pa.Has(attribute) {
			s.ProvisionableAttributes[attribute] = value
		}
	}
}

// writeDutState writes a JSON-encoded DutState proto to the cache file inside
// the autotest directory.
func writeDutState(autotestDir string, dutID string, s *lab_platform.DutState) error {
	p := dutstate.CacheFilePath(autotestDir, dutID)

	if err := writeJSONPb(p, s); err != nil {
		return errors.Annotate(err, "write DUT state").Err()
	}

	return nil
}
