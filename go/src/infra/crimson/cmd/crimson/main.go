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
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/maruel/subcommands"
	"golang.org/x/net/context"
	"google.golang.org/grpc"

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

type vlanFlags struct {
	commonFlags
	site      string
	vlanID    uint
	vlanAlias string
}

type addVlanRun struct {
	vlanFlags
	inputFileDHCP string
}

type queryVlanRun struct {
	vlanFlags
	limit int
	ip    string
}

type deleteVlanRun struct {
	commonFlags
	site   string
	vlanID uint
}

type hostFlags struct {
	commonFlags
	site      string
	hostname  string
	macAddr   string
	ip        string
	bootClass string
}

type addHostRun struct {
	hostFlags
	inputFileCSV string
}

type queryHostRun struct {
	hostFlags
	limit int
}

type deleteHostRun struct {
	commonFlags
	hostname     string
	macAddr      string
	inputFileCSV string
}

const backendHost = "crimson-staging.appspot.com"

func commonFlagVars(c *commonFlags) {
	c.Flags.StringVar(&c.backendHost, "backend-host",
		backendHost, "Host to talk to")
	c.Flags.Var(&c.format, "format", "Output format: "+
		cmdhelper.FormatTypeEnum.Choices())
	c.format = cmdhelper.DefaultFormat
}

func vlanFlagVars(c *vlanFlags) {
	commonFlagVars(&c.commonFlags)
	c.Flags.StringVar(&c.site, "site", "", "Name of the site")
	c.Flags.UintVar(&c.vlanID, "vlan-id", 0,
		"vlan number 1-4094, as defined by IEEE 802.1Q standard")
	c.Flags.StringVar(&c.vlanAlias, "vlan-alias", "",
		"Name of the vlan (usually suffix like -m1)")
}

func hostFlagVars(c *hostFlags) {
	commonFlagVars(&c.commonFlags)
	c.Flags.StringVar(&c.site, "site", "", "Name of the site")
	c.Flags.StringVar(&c.hostname, "hostname", "", "Name of the host")
	c.Flags.StringVar(&c.macAddr, "mac", "",
		"Host MAC address, as xx:xx:xx:xx:xx:xx")
	c.Flags.StringVar(&c.ip, "ip", "", "IP address")
	// The valid values here are application-specific and must be checked
	// server-side.
	c.Flags.StringVar(&c.bootClass, "boot-class", "", "Host boot class")
}

var (
	cmdCreateVlan = &subcommands.Command{
		UsageLine: "add-vlan <start ip>-<end ip>",
		ShortDesc: "Creates an IP range.",
		LongDesc:  "Creates an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &addVlanRun{}
			vlanFlagVars(&c.vlanFlags)
			c.Flags.StringVar(&c.inputFileDHCP, "input-file-dhcp", "",
				"Path to a dchpd.conf file containing subnet entries.")
			// The remaining argument is the IP range (ex: "192.168.0.1-192.168.0.5")
			return c
		},
	}

	cmdQueryVlan = &subcommands.Command{
		UsageLine: "query-vlan",
		ShortDesc: "Reads an IP range.",
		LongDesc:  "Reads an IP range.",
		CommandRun: func() subcommands.CommandRun {
			c := &queryVlanRun{}
			vlanFlagVars(&c.vlanFlags)
			c.Flags.StringVar(&c.ip, "ip", "", "IP contained within the range")
			// TODO(pgervais): tell the user when more results are available.
			c.Flags.IntVar(&c.limit, "limit", 1000,
				"Maximum number of results to return")
			return c
		},
	}

	cmdDeleteVlan = &subcommands.Command{
		UsageLine: "delete-vlan -site <site> -vlan-id <id>",
		ShortDesc: "Deletes a VLAN.",
		LongDesc:  "Deletes a VLAN.",
		CommandRun: func() subcommands.CommandRun {
			c := &deleteVlanRun{}
			commonFlagVars(&c.commonFlags)
			c.Flags.StringVar(&c.site, "site", "", "Name of the site")
			c.Flags.UintVar(&c.vlanID, "vlan-id", 0,
				"vlan number 1-4094, as defined by IEEE 802.1Q standard")
			return c
		},
	}

	cmdCreateHost = &subcommands.Command{
		UsageLine: "add-host",
		ShortDesc: "Creates host entries.",
		LongDesc:  "Creates host entries",
		CommandRun: func() subcommands.CommandRun {
			c := &addHostRun{}
			hostFlagVars(&c.hostFlags)
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
			hostFlagVars(&c.hostFlags)
			c.Flags.IntVar(&c.limit, "limit", 1000,
				"Maximum number of results to return")
			return c
		},
	}

	cmdDeleteHost = &subcommands.Command{
		UsageLine: "delete-host",
		ShortDesc: "Deletes host entries.",
		LongDesc:  "Deletes host entries",
		CommandRun: func() subcommands.CommandRun {
			c := &deleteHostRun{}
			commonFlagVars(&c.commonFlags)
			c.Flags.StringVar(&c.hostname, "hostname", "", "Name of the host")
			c.Flags.StringVar(&c.macAddr, "mac", "",
				"Host MAC address, as xx:xx:xx:xx:xx:xx")
			c.Flags.StringVar(&c.inputFileCSV, "input-file-csv", "",
				"CSV file containing one 'site,hostname,mac,ip[,boot_class]' per line. Only hostname and mac values are used.")
			return c
		},
	}
)

func ipRangeFromSiteAndVlan(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("missing required -site option")
	}

	if c.vlanID == 0 {
		return nil, fmt.Errorf("missing required -vlan-id option")
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
		Site:      c.site,
		VlanId:    uint32(c.vlanID),
		VlanAlias: c.vlanAlias,
		StartIp:   parts[0],
		EndIp:     parts[1]},
	}, nil
}

func ipRangeFromDhcpConfig(c *addVlanRun) ([]*crimson.IPRange, error) {
	if c.site == "" {
		return nil, fmt.Errorf("Missing required -site option.")
	}

	fmt.Fprintf(os.Stderr, "Reading %s... ", c.inputFileDHCP)
	file, err := os.Open(c.inputFileDHCP)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	ranges, err := cmdhelper.ReadDhcpdConfFile(file, c.site)
	if err != nil {
		return nil, err
	}
	fmt.Fprintf(os.Stderr, "Done.\n")
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
		// TODO(pgervais): display ranges found and ask user before proceeding.
	} else {
		ranges, err = ipRangeFromSiteAndVlan(c)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s\n", err)
			return 1
		}
	}
	cmdhelper.PrintIPRange(ranges, c.format)

	for _, req := range ranges {
		_, err := client.CreateIPRange(ctx, req)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
	}
	// TODO(pgervais): provide some useful feedback to the user.
	return 0
}

func (c *queryVlanRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	req := &crimson.IPRangeQuery{
		Site:      c.site,
		VlanId:    uint32(c.vlanID),
		VlanAlias: c.vlanAlias,
		Ip:        c.ip,
		Limit:     uint32(c.limit),
	}

	results, err := client.ReadIPRange(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}

	cmdhelper.PrintIPRange(results.Ranges, c.format)
	return 0
}

func (c *deleteVlanRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	req := &crimson.IPRangeDeleteList{
		Ranges: []*crimson.IPRangeDelete{{
			Site:   c.site,
			VlanId: uint32(c.vlanID),
		}}}

	_, err := client.DeleteIPRange(ctx, req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func hostListFromFile(filename string) (*crimson.HostList, error) {
	fmt.Fprintf(os.Stderr, "Reading %s... ", filename)
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	hostList, err := cmdhelper.ReadCSVHostFile(file)
	if err != nil {
		return nil, err
	}
	fmt.Fprintln(os.Stderr, "Done.")

	return hostList, nil
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
	return hostListFromFile(c.inputFileCSV)
}

func (c *addHostRun) Run(a subcommands.Application, args []string) int {
	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	hostList, err := hostListFromRangeFromArgs(c)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s\n", err)
		return 1
	}

	_, err = client.CreateHost(ctx, hostList)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s\n", grpc.ErrorDesc(err))
		return 1
	}
	// TODO(pgervais): provide some more useful feedback to the user.
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

func hostDeleteListFromFile(file string) (*crimson.HostDeleteList, error) {
	hostList, err := hostListFromFile(file)
	if err != nil {
		return nil, err
	}
	hdl := &crimson.HostDeleteList{}
	for _, host := range hostList.Hosts {
		hdl.Hosts = append(hdl.Hosts, &crimson.HostDelete{
			Hostname: host.Hostname,
			MacAddr:  host.MacAddr,
		})
	}
	return hdl, nil
}

func hostDeleteListFromArgs(c *deleteHostRun) (*crimson.HostDeleteList, error) {
	if c.hostname == "" && c.macAddr == "" {
		return nil, fmt.Errorf("at least one of -hostname or -mac option is required")
	}

	hdl := &crimson.HostDeleteList{
		Hosts: []*crimson.HostDelete{{
			Hostname: c.hostname,
			MacAddr:  c.macAddr,
		}}}
	return hdl, nil
}

func (c *deleteHostRun) Run(a subcommands.Application, args []string) int {
	var hostList *crimson.HostDeleteList
	var err error

	if c.inputFileCSV == "" {
		hostList, err = hostDeleteListFromArgs(c)
	} else {
		hostList, err = hostDeleteListFromFile(c.inputFileCSV)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s\n", err)
		return 1
	}

	ctx := cli.GetContext(a, c)
	client := c.newCrimsonClient(ctx)

	_, err = client.DeleteHost(ctx, hostList)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s\n", err)
		return 1
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
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			authcli.SubcommandInfo(opts, "info"),
			authcli.SubcommandLogin(opts, "login"),
			authcli.SubcommandLogout(opts, "logout"),
			cmdCreateVlan,
			cmdQueryVlan,
			cmdDeleteVlan,
			cmdCreateHost,
			cmdQueryHost,
			cmdDeleteHost,
		},
	}
	status := subcommands.Run(application, nil)
	if status == 0 {
		fmt.Fprintln(os.Stderr, "Success")
	} else {
		fmt.Fprintf(os.Stderr, "*** FAILURE (status %d) ***\n", status)
	}
	os.Exit(status)
}
