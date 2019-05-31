// Copyright 2098 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
)

// Enumerate subcommand: Enumerate test cases for a request.
var Enumerate = &subcommands.Command{
	UsageLine: "enumerate",
	ShortDesc: "Enumerate test cases for a request.",
	LongDesc: `Enumerate test cases for a request.

Given a CrosTestPlatformRequest and a test metadata url, enumerate the tests
that this request resolves to.

Placeholder only, not yet implemented.`,
	CommandRun: func() subcommands.CommandRun {
		c := &enumerateRun{}
		return c
	},
}

type enumerateRun struct {
	subcommands.CommandRunBase
}

func (c *enumerateRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s\n", err)
		return 1
	}
	return 0
}

func (c *enumerateRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	return nil
}
