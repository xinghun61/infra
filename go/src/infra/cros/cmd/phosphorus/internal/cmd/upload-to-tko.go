// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// UploadToTKO subcommand: Parse test results and upload them to TKO.
var UploadToTKO = &subcommands.Command{
	UsageLine: "upload-to-tko",
	ShortDesc: "Parse test results and upload them to TKO.",
	LongDesc: `Parse test results and upload them to TKO.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &uploadToTKORun{}
		return c
	},
}

type uploadToTKORun struct {
	subcommands.CommandRunBase
}

func (c *uploadToTKORun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *uploadToTKORun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
