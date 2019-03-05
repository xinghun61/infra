// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"
	"os"

	"github.com/maruel/subcommands"

	"infra/libs/skylab/inventory"
)

// ListDuplicates implements the list-duplicates subcommand.
var ListDuplicates = &subcommands.Command{
	UsageLine: "list-duplicates -root DATA_DIR",
	ShortDesc: "list duplicate DUTs between Autotest and Skylab",
	LongDesc: `List duplicate DUTs between Autotest and Skylab.

DATA_DIR should point to the top directory of a skylab_inventory data
checkout. Skylab data is then located at ${DATA_DIR}/data/skylab`,
	CommandRun: func() subcommands.CommandRun {
		c := &listDuplicatesRun{}
		c.Flags.StringVar(&c.rootDir, "root", "", "root `directory` of the inventory checkout")
		return c
	},
}

type listDuplicatesRun struct {
	subcommands.CommandRunBase
	rootDir string
}

func (c *listDuplicatesRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

func (c *listDuplicatesRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.rootDir == "" {
		return errors.New("-root is required")
	}

	labs, err := loadAllLabsData(c.rootDir)
	if err != nil {
		return err
	}
	skDUTs := dutNamesInLab(labs.Skylab)
	listDuplicates(skDUTs, labs.AutotestProd)
	listDuplicates(skDUTs, labs.AutotestDev)
	return nil
}

func listDuplicates(skDUTs map[string]bool, lab *inventory.Lab) {
	for _, d := range lab.GetDuts() {
		h := d.GetCommon().GetHostname()
		if skDUTs[h] {
			fmt.Println(h)
		}
	}
}

func dutNamesInLab(lab *inventory.Lab) map[string]bool {
	m := make(map[string]bool)
	for _, d := range lab.Duts {
		m[d.GetCommon().GetHostname()] = true
	}
	return m
}
