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
	format      cmdhelper.FormatType
}

type addVlanRun struct {
	commonFlags
	site          string
	vlan          string
	inputFileDHCP string
}

type queryVlanRun struct {
	commonFlags
	limit int
	site  string
	vlan  string
	ip    string
}

type addHostRun struct {
	commonFlags
	site         string
	hostname     string
	macAddr      string
	ip           string
	bootClass    string
	inputFileCSV string
}

type queryHostRun struct {
	commonFlags
	limit     int
	site      string
	hostname  string
	macAddr   string
	ip        string
	bootClass string
}

const backendHost = "crimson-staging.appspot.com"

var (
	cmdCreateIPRange = &subcommands.Command{
		UsageLine: "add-vlan <start ip>-<end ip>",
		ShortDesc: "Creates an IP range.",
		LongDesc:  "Creates an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &addVlanRun{}
			c.Flags.StringVar(&c.backendHost, "backend-host",
				backendHost, "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.vlan, "vlan", "", "Name of the vlan")
			c.Flags.StringVar(&c.inputFileDHCP, "input-file-dhcp", "",
				"Path to a dchpd.conf file containing subnet entries.")
			c.Flags.Var(&c.format, "format", "Output format: "+
				cmdhelper.FormatTypeEnum.Choices())
			// The remaining argument is the IP range (ex: "192.168.0.1-192.168.0.5")
			return c
		},
	}

	cmdQueryIPRange = &subcommands.Command{
		UsageLine: "query-vlan",
		ShortDesc: "Reads an IP range.",
		LongDesc:  "Reads an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &queryVlanRun{}
			c.format = cmdhelper.DefaultFormat
			c.Flags.StringVar(&c.backendHost, "backend-host",
				backendHost, "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.vlan, "vlan", "", "Name of the vlan")
			c.Flags.StringVar(&c.ip, "ip", "", "IP contained within the range")
			// TODO(pgervais): tell the user when more results are available.
			c.Flags.IntVar(&c.limit, "limit", 1000,
				"Maximum number of results to return")
			c.Flags.Var(&c.format, "format", "Output format: "+
				cmdhelper.FormatTypeEnum.Choices())
			return c
		},
	}

	cmdCreateHost = &subcommands.Command{
		UsageLine: "add-host",
		ShortDesc: "Creates host entries.",
		LongDesc:  "Creates host entries",
		CommandRun: func() subcommands.CommandRun {
			c := &addHostRun{}
			c.Flags.StringVar(&c.backendHost, "backend-host",
				backendHost, "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.hostname, "hostname", "", "Name of the host")
			c.Flags.StringVar(&c.macAddr, "mac", "",
				"Host MAC address, as xx:xx:xx:xx:xx:xx")
			c.Flags.StringVar(&c.ip, "ip", "", "IP address")
			// The valid values here are application-specific and must be checked
			// server-side.
			c.Flags.StringVar(&c.bootClass, "boot-class", "", "Host boot class")
			c.Flags.StringVar(&c.inputFileCSV, "input-file-csv", "",
				"CSV file containing one 'site,hostname,mac,ip[,boot_class]' per line.")
			return c
		},
	}

	cmdQueryHost = &subcommands.Command{
		UsageLine: "query-host",
		ShortDesc: "Reads hosts.",
		LongDesc:  "Fetches a filtered list of hosts.",
		CommandRun: func() subcommands.CommandRun {
			c := &queryHostRun{}
			c.format = cmdhelper.DefaultFormat
			c.Flags.StringVar(&c.backendHost, "backend-host",
				backendHost, "Host to talk to")
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.StringVar(&c.hostname, "hostname", "", "Name of the host")
			c.Flags.StringVar(&c.macAddr, "mac", "",
				"Host MAC address, as xx:xx:xx:xx:xx:xx")
			c.Flags.StringVar(&c.ip, "ip", "", "IP address")
			// The valid values here are application-specific and must be checked
			// server-side.
			c.Flags.StringVar(&c.bootClass, "boot-class", "", "Host boot class")
			c.Flags.Var(&c.format, "format", "Output format: "+
				cmdhelper.FormatTypeEnum.Choices())
			c.Flags.IntVar(&c.limit, "limit", 1000,
				"Maximum number of results to return")
			return c
		},
	}
)

func ipRangeFromSiteAndVlan(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("missing required -site option")
	}

	if c.vlan == "" {
		return nil, fmt.Errorf("missing required -vlan option")
	}

	if c.Flags.NArg() == 0 {
		return nil, fmt.Errorf(
			"missing an IP range. Example: '192.168.0.0-192.168.0.5'")
	}
	parts := strings.SplitN(c.Flags.Args()[0], "-", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got %s", c.Flags.Args()[0])
	}

	if ip := net.ParseIP(parts[0]); ip == nil {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got %s", c.Flags.Args()[0])
	}

	if ip := net.ParseIP(parts[1]); ip == nil {
		return nil, fmt.Errorf(
			"invalid format for ipRange. Expecting something like "+
				"'192.168.0.0-192.168.0.5', got %s", c.Flags.Args()[0])
	}

	return []*crimson.IPRange{{
		Site:    c.site,
		Vlan:    c.vlan,
		StartIp: parts[0],
		EndIp:   parts[1]},
	}, nil
}

func ipRangeFromDhcpConfig(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("Missing required -site option.")
	}

	var ranges []*crimson.IPRange

	fmt.Fprintf(os.Stderr, "Reading %s... ", c.inputFileDHCP)
	file, err := os.Open(c.inputFileDHCP)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	subnets, err := cmdhelper.ReadDhcpdConfFile(file)
	if err != nil {
		return nil, err
	}
	fmt.Fprintf(os.Stderr, "Done.\n")
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
		cmdhelper.PrintIPRange(ranges, c.format)
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
		Ip:    c.ip,
		Limit: uint32(c.limit),
	}

	results, err := client.ReadIPRange(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	cmdhelper.PrintIPRange(results.Ranges, c.format)
	return 0
}

func hostListFromRangeFromArgs(c *addHostRun) (*crimson.HostList, error) {
	if c.inputFileCSV == "" {
		if c.site == "" {
			return nil, fmt.Errorf("missing required -site option")
		}

		if c.hostname == "" {
			return nil, fmt.Errorf("missing required -hostname option")
		}

		if c.macAddr == "" {
			return nil, fmt.Errorf("missing required -mac option")
		}

		if c.ip == "" {
			return nil, fmt.Errorf("missing required -ip option")
		}
		hostList := crimson.HostList{
			Hosts: []*crimson.Host{{
				Site:      c.site,
				Hostname:  c.hostname,
				MacAddr:   c.macAddr,
				Ip:        c.ip,
				BootClass: c.bootClass,
			}}}
		return &hostList, nil

	}
	if c.site != "" || c.hostname != "" || c.macAddr != "" || c.ip != "" {
		fmt.Fprintf(os.Stderr,
			"-input-file-csv has been provided, any of -site, -hostname, "+
				"-mac, -ip will be ignored.")
	}
	fmt.Fprintf(os.Stderr, "Reading %s... ", c.inputFileCSV)
	file, err := os.Open(c.inputFileCSV)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	hostList, err := cmdhelper.ReadCSVHostFile(file)
	if err != nil {
		return nil, err
	}
	fmt.Fprintf(os.Stderr, "Done.\n")

	return hostList, nil
}

func (c *addHostRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	hostList, err := hostListFromRangeFromArgs(c)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s\n", err)
		return 1
	}

	_, err = client.CreateHost(ctx, hostList)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	// TODO(pgervais): provide some more useful feedback to the user.
	fmt.Println("Success.")
	return 0
}

func (c *queryHostRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	req := &crimson.HostQuery{
		Limit:     uint32(c.limit),
		Site:      c.site,
		Hostname:  c.hostname,
		MacAddr:   c.macAddr,
		Ip:        c.ip,
		BootClass: c.bootClass,
	}

	hostList, err := client.ReadHost(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	cmdhelper.PrintHostList(hostList, c.format)
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
			cmdQueryIPRange,
			cmdCreateHost,
			cmdQueryHost,
		},
	}
	os.Exit(subcommands.Run(application, nil))
}
