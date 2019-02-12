// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"fmt"
	"strings"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/cipd"
	"infra/cmd/skylab/internal/site"
)

// Version subcommand: Version skylab tool.
var Version = &subcommands.Command{
	UsageLine: "version",
	ShortDesc: "print skylab tool version",
	LongDesc:  "Print skylab tool version.",
	CommandRun: func() subcommands.CommandRun {
		c := &versionRun{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		return c
	},
}

type versionRun struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
}

func (c *versionRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.innerRun(a, args, env); err != nil {
		fmt.Fprintf(a.GetErr(), "%s: %s\n", progName, err)
		return 1
	}
	return 0
}

func (c *versionRun) innerRun(a subcommands.Application, args []string, env subcommands.Env) error {
	d, err := executableDir()
	if err != nil {
		return err
	}
	root, err := findCIPDRootDir(d)
	if err != nil {
		return err
	}
	pkgs, err := cipd.InstalledPackages(cipd.CmdClient{}, root)
	if err != nil {
		return err
	}
	for _, p := range pkgs {
		if !strings.HasPrefix(p.Package, "chromiumos/infra/skylab/") {
			continue
		}
		fmt.Printf("%s\t%s\ttracking %s\n", p.Package, p.Pin.InstanceID, p.Tracking)
		return nil
	}
	return errors.Reason("could not find installed skylab CIPD package").Err()
}
