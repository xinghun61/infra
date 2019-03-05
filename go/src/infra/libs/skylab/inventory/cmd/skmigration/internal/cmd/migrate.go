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

// Migrate implements the migrate subcommand.
var Migrate = &subcommands.Command{
	UsageLine: "migrate -root DATA_DIR HOSTNAME [HOSTNAME...]",
	ShortDesc: "migrate DUTs from Autotest to Skylab",
	LongDesc: `Migrate DUTs from Autotest to Skylab.

migrate adds the DUT to Skylab, but does not delete it from Autotest.

DATA_DIR should point to the top directory of a skylab_inventory data
checkout. Skylab data is then located at ${DATA_DIR}/data/skylab`,
	CommandRun: func() subcommands.CommandRun {
		c := &migrateRun{}
		c.Flags.StringVar(&c.rootDir, "root", "", "root `directory` of the inventory checkout")
		c.Flags.BoolVar(&c.fromDev, "fromdev", false, "migrate from Autotest dev environment")
		return c
	},
}

type migrateRun struct {
	subcommands.CommandRunBase
	rootDir string
	fromDev bool
}

func (c *migrateRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}
	return 0
}

func (c *migrateRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	if c.rootDir == "" {
		return errors.New("-root is required")
	}
	if len(args) == 0 {
		return errors.New("must specify at least one HOSTNAME")
	}

	labs, err := loadAllLabsData(c.rootDir)
	if err != nil {
		return err
	}

	hostnames := stringSet(args)
	existing := dutsInSet(labs.Skylab, hostnames)
	if len(existing) > 0 {
		return fmt.Errorf("DUTs already exist: %s", existing)
	}

	var fromLab *inventory.Lab
	if c.fromDev {
		fromLab = labs.AutotestDev
	} else {
		fromLab = labs.AutotestProd
	}

	for _, d := range fromLab.GetDuts() {
		h := d.GetCommon().GetHostname()
		if hostnames[h] {
			labs.Skylab.Duts = append(labs.Skylab.Duts, d)
			delete(hostnames, h)
		}
	}

	if len(hostnames) > 0 {
		return fmt.Errorf("could not find hosts: %s", getKeys(hostnames))
	}
	return writeSkylabLabData(c.rootDir, labs)
}

func stringSet(args []string) map[string]bool {
	hs := make(map[string]bool)
	for _, h := range args {
		hs[h] = true
	}
	return hs
}

func dutsInSet(lab *inventory.Lab, hostnames map[string]bool) []string {
	existing := []string{}
	for _, d := range lab.GetDuts() {
		h := d.GetCommon().GetHostname()
		if hostnames[h] {
			existing = append(existing, h)
		}
	}
	return existing
}

func getKeys(m map[string]bool) []string {
	ks := make([]string, 0, len(m))
	for k := range m {
		ks = append(ks, k)
	}
	return ks
}
