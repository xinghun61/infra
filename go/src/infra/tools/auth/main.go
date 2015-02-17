// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
CLI wrapper for infra/libs/auth library. Can be used to manage cached
credentials.
*/
package main

import (
	"os"

	"infra/libs/auth"
	"infra/libs/build"

	"github.com/maruel/subcommands"
)

var application = &subcommands.DefaultApplication{
	Name:  "auth",
	Title: "Chrome Infra Authentication tool " + build.InfoString(),
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,

		auth.SubcommandInfo("info"),
		auth.SubcommandLogin("login"),
		auth.SubcommandLogout("logout"),
	},
}

func main() {
	os.Exit(subcommands.Run(application, nil))
}
