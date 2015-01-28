// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
CLI wrapper for infra/libs/auth library. Can be used to manage cached
credentials.
*/
package main

import (
	"fmt"
	"net/http"
	"os"

	"infra/libs/auth"

	"github.com/Sirupsen/logrus"
	"github.com/maruel/subcommands"
)

func reportIdentity(t http.RoundTripper) error {
	var ident auth.Identity
	service, err := auth.NewGroupsService("", &http.Client{Transport: t}, nil)
	if err == nil {
		ident, err = service.FetchCallerIdentity()
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to fetch current identity: %s\n", err)
		return err
	}
	fmt.Printf("Logged in as %s\n", ident)
	return nil
}

////////////////////////////////////////////////////////////////////////////////
// 'login' subcommand.

var cmdLogin = &subcommands.Command{
	UsageLine: "login",
	ShortDesc: "performs interactive login flow",
	LongDesc:  "Performs interactive login flow and caches obtained credentials",
	CommandRun: func() subcommands.CommandRun {
		return &loginRun{}
	},
}

type loginRun struct {
	subcommands.CommandRunBase
}

func (c *loginRun) Run(a subcommands.Application, args []string) int {
	transport, err := auth.LoginIfRequired(nil)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Login failed: %s\n", err.Error())
		return 1
	}
	err = reportIdentity(transport)
	if err != nil {
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////
// 'logout' subcommand.

var cmdLogout = &subcommands.Command{
	UsageLine: "logout",
	ShortDesc: "removes cached credentials",
	LongDesc:  "Removes cached credentials from the disk",
	CommandRun: func() subcommands.CommandRun {
		return &logoutRun{}
	},
}

type logoutRun struct {
	subcommands.CommandRunBase
}

func (c *logoutRun) Run(a subcommands.Application, args []string) int {
	err := auth.PurgeCredentialsCache()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////
// 'info' subcommand.

var cmdInfo = &subcommands.Command{
	UsageLine: "info",
	ShortDesc: "prints an email address associated with currently cached token",
	LongDesc:  "Prints an email address associated with currently cached token",
	CommandRun: func() subcommands.CommandRun {
		return &infoRun{}
	},
}

type infoRun struct {
	subcommands.CommandRunBase
}

func (c *infoRun) Run(a subcommands.Application, args []string) int {
	transport, err := auth.DefaultAuthenticator.Transport()
	if err == auth.ErrLoginRequired {
		fmt.Fprintln(os.Stderr, "Not logged in")
		return 1
	} else if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	err = reportIdentity(transport)
	if err != nil {
		return 3
	}
	return 0
}

////////////////////////////////////////////////////////////////////////////////
// Main.

var application = &subcommands.DefaultApplication{
	Name:  "auth",
	Title: "Chrome Infra Authentication tool.",
	Commands: []*subcommands.Command{
		subcommands.CmdHelp,

		cmdInfo,
		cmdLogin,
		cmdLogout,
	},
}

func main() {
	logrus.SetLevel(logrus.DebugLevel)
	os.Exit(subcommands.Run(application, nil))
}
