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

	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/logging/gologger"

	"github.com/maruel/subcommands"
)

func main() {
	opts := auth.Options{Logger: gologger.Get()}
	application := &subcommands.DefaultApplication{
		Name:  "auth",
		Title: "Chrome Infra Authentication tool",
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			auth.SubcommandInfo(opts, "info"),
			auth.SubcommandLogin(opts, "login"),
			auth.SubcommandLogout(opts, "logout"),
		},
	}
	os.Exit(subcommands.Run(application, nil))
}
