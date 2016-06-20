// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"os"
	"regexp"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/prpc"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"infra/crimson/proto"
)

type commonFlags struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	backendHost string
}

type addVlanRun struct {
	commonFlags
	site string
	vlan string
}

type queryVlanRun struct {
	commonFlags
	site  string
	vlan  string
	limit int
}

var (
	cmdCreateIPRange = &subcommands.Command{
		UsageLine: "add-vlan <start ip>-<end ip>",
		ShortDesc: "Creates an IP range.",
		LongDesc:  "Creates an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &addVlanRun{}
			c.Flags.StringVar(&c.backendHost, "backend-host",
				"crimson-staging.appspot.com", "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.vlan, "vlan", "", "Name of the vlan")
			// The remaining argument is the IP range (ex: "192.168.0.1-192.168.0.5")
			return c
		},
	}

	cmdReadIPRange = &subcommands.Command{
		UsageLine: "query-vlan",
		ShortDesc: "Reads an IP range.",
		LongDesc:  "Reads an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &queryVlanRun{}
			c.Flags.StringVar(&c.backendHost, "backend-host",
				"crimson-staging.appspot.com", "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.vlan, "vlan", "", "Name of the vlan")
			c.Flags.IntVar(&c.limit, "limit", 10,
				"Maximum number of results to return")
			return c
		},
	}
)

func (c *addVlanRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	if c.site == "" {
		fmt.Fprintln(os.Stderr,
			"Missing required --site option.")
		return 1
	}

	if c.vlan == "" {
		fmt.Fprintln(os.Stderr,
			"Missing required --vlan option.")
		return 1
	}

	if c.Flags.NArg() == 0 {
		fmt.Fprintln(os.Stderr,
			"Missing an IP range. Example: '192.168.0.0-192.168.0.5'.")
		return 1
	}
	ipParser := regexp.MustCompile(
		`^([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+)[-]([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+)$`)
	parts := ipParser.FindStringSubmatch(c.Flags.Args()[0])
	if parts == nil {
		fmt.Fprintln(os.Stderr,
			"Invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got ", c.Flags.Args()[0])
		return 1
	}

	req := &crimson.IPRange{
		Site:    c.site,
		Vlan:    c.vlan,
		StartIp: parts[1],
		EndIp:   parts[2],
	}
	res, err := client.CreateIPRange(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	// TODO(pgervais): provide some useful feedback to the user.
	fmt.Println(res)
	return 0
}

func (c *queryVlanRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	req := &crimson.IPRangeQuery{
		Site:  c.site,
		Vlan:  c.vlan,
		Limit: uint32(c.limit),
	}

	results, err := client.ReadIPRange(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	fmt.Println("site \tvlan \t IP range")
	for _, ipRange := range results.Ranges {
		fmt.Printf("%s \t %s \t%s-%s\n",
			ipRange.Site, ipRange.Vlan, ipRange.StartIp, ipRange.EndIp)
	}
	return 0
}

func (c *commonFlags) newCrimsonClient(ctx context.Context) crimson.CrimsonClient {
	authOpts, err := c.authFlags.Options()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to get auth options")
		return nil
	}

	httpClient, err := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts).Client()

	if err != nil {
		fmt.Fprintln(os.Stderr, "Failed to get authenticator")
		return nil
	}
	client := crimson.NewCrimsonPRPCClient(
		&prpc.Client{
			C:    httpClient,
			Host: c.backendHost})
	return client
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
			cmdCreateIPRange,
			cmdReadIPRange,
		},
	}
	os.Exit(subcommands.Run(application, nil))
}
