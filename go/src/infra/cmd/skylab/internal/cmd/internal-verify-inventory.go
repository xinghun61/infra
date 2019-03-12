// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"os"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/inventory"
)

// InternalVerifyInventory subcommand: Verify inventory.
var InternalVerifyInventory = &subcommands.Command{
	UsageLine: "internal-verify-inventory DATA_DIR",
	ShortDesc: "Verify skylab inventory.",
	LongDesc: `Verify skylab inventory.

For internal use only.`,
	CommandRun: func() subcommands.CommandRun {
		return &internalVerifyInventory{}
	},
}

type internalVerifyInventory struct {
	subcommands.CommandRunBase
}

func (c *internalVerifyInventory) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), errors.Annotate(err, "internal-verify-inventory").Err())
		return 1
	}
	return 0
}

func (c *internalVerifyInventory) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if len(args) != 1 {
		return NewUsageError(c.Flags, "want 1 positional argument, have %d", len(args))
	}
	ddir := args[0]
	if _, err := os.Stat(ddir); os.IsNotExist(err) {
		return err
	}
	if err := inventory.VerifyLabInventory(ddir); err != nil {
		return err
	}
	if err := inventory.VerifyInfraInventory(ddir); err != nil {
		return err
	}
	return nil
}
