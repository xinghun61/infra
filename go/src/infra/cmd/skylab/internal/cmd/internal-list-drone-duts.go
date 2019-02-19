// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"

	"infra/cmd/skylab/internal/site"
	"infra/libs/skylab/inventory"
)

// InternalListDroneDuts subcommand: List DUTs for a drone.
var InternalListDroneDuts = &subcommands.Command{
	UsageLine: "internal-list-drone-duts",
	ShortDesc: "list DUTs for a drone",
	LongDesc: `List DUTs for a drone.

For internal use only.`,
	CommandRun: func() subcommands.CommandRun {
		c := &internalListDroneDutsRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.Flags.StringVar(&c.dataDir, "datadir", "", "Path to the directory containing skylab inventory data.")
		c.Flags.StringVar(&c.hostname, "hostname", "", "FQDN of the drone.")
		return c
	},
}

type internalListDroneDutsRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	dataDir   string
	hostname  string
}

func (c *internalListDroneDutsRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *internalListDroneDutsRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	ddir, err := inventory.ReadSymlink(c.dataDir)
	if err != nil {
		return err
	}
	inf, err := inventory.LoadInfrastructure(ddir)
	if err != nil {
		return err
	}
	var dutIDs []string
	for _, s := range inf.GetServers() {
		if s.GetHostname() == c.hostname {
			dutIDs = s.GetDutUids()
			break
		}
	}
	if len(dutIDs) == 0 {
		return nil
	}
	lab, err := inventory.LoadLab(ddir)
	if err != nil {
		return err
	}
	dutNames := make(map[string]string)
	for _, d := range lab.GetDuts() {
		c := d.GetCommon()
		dutNames[c.GetId()] = c.GetHostname()
	}
	for _, id := range dutIDs {
		fmt.Println(id, dutNames[id])
	}
	return nil
}
