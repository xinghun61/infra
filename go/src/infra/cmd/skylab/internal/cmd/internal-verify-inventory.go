// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"os"
	"strings"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/errors"

	"infra/libs/skylab/inventory"
)

// InternalVerifyInventory subcommand: Verify inventory.
var InternalVerifyInventory = &subcommands.Command{
	UsageLine: "internal-verify-inventory [-inv-type TYPE]... DATA_DIR",
	ShortDesc: "verify skylab inventory.",
	LongDesc: `Verify skylab inventory.

For internal use only.`,
	CommandRun: func() subcommands.CommandRun {
		c := &internalVerifyInventory{}
		c.Flags.Var(&c.typeToVerify, "inv-type", inventoryTypeUsage())
		return c
	},
}

// Inventory types defined in package `inventory`.
type inventoryTypes uint

//go:generate stringer -type inventoryTypes

const (
	inventoryTypeLab inventoryTypes = 1 << iota
	inventoryTypeInfra
)

const allInventoryTypes = inventoryTypeLab | inventoryTypeInfra

var inventoryTypeNameDict = map[string]inventoryTypes{
	"lab":   inventoryTypeLab,
	"infra": inventoryTypeInfra,
}

func inventoryTypeUsage() string {
	keys := make([]string, 0, len(inventoryTypeNameDict))
	for k := range inventoryTypeNameDict {
		keys = append(keys, k)
	}
	return fmt.Sprintf("Inventory type to verify. This flag can be used "+
		"multiple times. The type can be %s (case insensitive).", strings.Join(keys, ", "))

}

// Set is for flag.value of '-inv-type'.
func (i *inventoryTypes) Set(value string) error {
	v, ok := inventoryTypeNameDict[strings.ToLower(value)]
	if !ok {
		return fmt.Errorf("unsupported inventory type: %s", value)
	}
	*i |= v
	return nil
}

type internalVerifyInventory struct {
	subcommands.CommandRunBase
	typeToVerify inventoryTypes
}

func (c *internalVerifyInventory) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		PrintError(a.GetErr(), errors.Annotate(err, "internal-verify-inventory").Err())
		return 1
	}
	return 0
}

func (c *internalVerifyInventory) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if narg := c.Flags.NArg(); narg != 1 {
		return NewUsageError(c.Flags, "want 1 positional argument, have %d", narg)
	}
	ddir := c.Flags.Arg(0)
	if _, err := os.Stat(ddir); os.IsNotExist(err) {
		return err
	}

	if c.typeToVerify == 0 {
		c.typeToVerify = allInventoryTypes
	}
	var resultErrors []error
	if c.typeToVerify&inventoryTypeLab != 0 {
		if err := inventory.VerifyLabInventory(ddir); err != nil {
			resultErrors = append(resultErrors, err)
		}
	}
	if c.typeToVerify&inventoryTypeInfra != 0 {
		if err := inventory.VerifyInfraInventory(ddir); err != nil {
			resultErrors = append(resultErrors, err)
		}
	}
	switch len(resultErrors) {
	case 0:
		return nil
	case 1:
		return resultErrors[0]
	case 2:
		return errors.New(resultErrors[0].Error() + resultErrors[1].Error())
	default:
		panic("This shouldn't happen!")
	}
}
