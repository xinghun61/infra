// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net"
	"os"
	"strings"

	"github.com/luci/luci-go/client/authcli"
	"github.com/luci/luci-go/common/auth"
	"github.com/luci/luci-go/common/cli"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/common/prpc"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	"infra/crimson/cmd/cmdhelper"
	crimson "infra/crimson/proto"
)

// Flag definitions
type commonFlags struct {
	subcommands.CommandRunBase
	authFlags   authcli.Flags
	backendHost string
}

type addVlanRun struct {
	commonFlags
	site          string
	vlan          string
	inputFileDHCP string
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
			c.Flags.StringVar(&c.inputFileDHCP, "input-file-dhcp", "",
				"Path to a dchpd.conf file containing subnet entries.")
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

func ipRangeFromSiteAndVlan(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("missing required -site option.")
	}

	if c.vlan == "" {
		return nil, fmt.Errorf("missing required -vlan option.")
	}

	if c.Flags.NArg() == 0 {
		return nil, fmt.Errorf(
			"missing an IP range. Example: '192.168.0.0-192.168.0.5'.")
	}
	parts := strings.SplitN(c.Flags.Args()[0], "-", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got ", c.Flags.Args()[0])
	}

	if ip := net.ParseIP(parts[0]); ip == nil {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got ", c.Flags.Args()[0])
	}

	if ip := net.ParseIP(parts[1]); ip == nil {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got ", c.Flags.Args()[0])
	}

	return []*crimson.IPRange{{
		Site:    c.site,
		Vlan:    c.vlan,
		StartIp: parts[1],
		EndIp:   parts[2]},
	}, nil
}

func ipRangeFromDhcpConfig(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("Missing required -site option.")
	}

	var ranges []*crimson.IPRange

	fmt.Fprintf(os.Stderr, "Reading %s...\n", c.inputFileDHCP)
	file, err := os.Open(c.inputFileDHCP)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	subnets, err := cmdhelper.ReadDhcpdConfFile(file)
	if err != nil {
		return nil, err
	}
	for _, subnet := range subnets {
		ranges = append(ranges, subnet.IPRanges(c.site)...)
	}
	return ranges, nil
}

func (c *addVlanRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	var ranges []*crimson.IPRange
	var err error

	if len(c.inputFileDHCP) > 0 {
		ranges, err = ipRangeFromDhcpConfig(c)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s\n", err)
			return 1
		}
		cmdhelper.PrintIPRange(ranges)
		// TODO(pgervais): display ranges found and ask user before proceeding.
	} else {
		ranges, err = ipRangeFromSiteAndVlan(c)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s\n", err)
			return 1
		}
	}

	for _, req := range ranges {
		_, err := client.CreateIPRange(ctx, req)
		// TODO: try everything even if it fails for some.
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
	}
	// TODO(pgervais): provide some useful feedback to the user.
	fmt.Println("Success.")
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

	cmdhelper.PrintIPRange(results.Ranges)
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
