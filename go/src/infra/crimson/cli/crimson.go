// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"os"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/prpc"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"infra/crimson/proto"
)

var (
	cmdEcho = &subcommands.Command{
		UsageLine: "echo <text>",
		ShortDesc: "sends a ping to Crimson.",
		LongDesc:  "Sends a ping to Crimson.",
		CommandRun: func() subcommands.CommandRun {
			c := &echoRun{}
			c.Flags.StringVar(&c.backendHost, "backend-host",
				"crimson-staging.appspot.com", "Host to talk to")
			return c
		},
	}
	// Hostname of the appengine app this tool communicates with.
)

type echoRun struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	backendHost string
}

func (c *echoRun) Run(a subcommands.Application, args []string) int {
	authOpts, err := c.authFlags.Options()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to get auth options")
		return 1
	}

	ctx := cli.GetContext(a, c)
	httpClient, err := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts).Client()

	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to get authenticator")
		return 1
	}
	greeter := crimson.NewGreeterPRPCClient(
		&prpc.Client{
			C:    httpClient,
			Host: c.backendHost})

	req := &crimson.HelloRequest{}
	if len(os.Args) > 1 {
		req.Name = os.Args[1]
	}

	res, err := greeter.SayHello(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	fmt.Println(res.Message)
	return 0
}

func main() {
	opts := auth.Options{}
	application := &cli.Application{
		Name:  "crimson",
		Title: "Crimson DB Command-line Interface",
		Context: func(ctx context.Context) context.Context {
			return gologger.StdConfig.Use(ctx)
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			authcli.SubcommandInfo(opts, "info"),
			authcli.SubcommandLogin(opts, "login"),
			authcli.SubcommandLogout(opts, "logout"),
			cmdEcho,
		},
	}
	os.Exit(subcommands.Run(application, nil))
}
