// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package datautil

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/luci/luci-go/common/flag/flagenum"

	crimson "infra/crimson/proto"
)

// Formatter formats tables for printing according to -format flag.
type Formatter interface {
	// FormatRows formats rows of a table as strings for pretty-printing.
	FormatRows(rows [][]string) []string
}

// FormatType is the type for enum values for the -format flag.
type FormatType string

var _ flag.Value = (*FormatType)(nil)

const (
	textFormat = FormatType("text")
	csvFormat  = FormatType("csv")
	jsonFormat = FormatType("json")
	dhcpFormat = FormatType("dhcp")
	// DefaultFormat is the default value to use for FormatType.
	DefaultFormat = textFormat
)

// FormatTypeEnum is the value type for the -format flag.
var FormatTypeEnum = flagenum.Enum{
	"text": textFormat,
	"csv":  csvFormat,
	"json": jsonFormat,
	"dhcp": dhcpFormat,
}

func (ft *FormatType) String() string {
	return FormatTypeEnum.FlagString(*ft)
}

// Set implements flag.Value
func (ft *FormatType) Set(v string) error {
	return FormatTypeEnum.FlagSet(ft, v)
}

// CSVFormatter formats output in CSV format.
type CSVFormatter struct{}

var _ Formatter = &CSVFormatter{}

// FormatRows prints all rows in CSV format.
func (f *CSVFormatter) FormatRows(rows [][]string) []string {
	var output []string
	for _, row := range rows {
		for i, val := range row {
			if strings.Contains(val, ",") {
				row[i] = `"` + val + `"`
			}
		}
		output = append(output, strings.Join(row, ","))
	}
	return output
}

// TextFormatter formats output as a pretty-printed text table.
type TextFormatter struct {
	lengths []int
}

var _ Formatter = &TextFormatter{}

func (f *TextFormatter) setSpacingFromRows(rows [][]string) {
	for _, cols := range rows {
		for i, col := range cols {
			if len(f.lengths) <= i {
				f.lengths = append(f.lengths, len(col))
			} else if f.lengths[i] < len(col) {
				f.lengths[i] = len(col)
			}
		}
	}
}

func (f *TextFormatter) formatRow(cols []string) string {
	s := bytes.Buffer{}
	for i, col := range cols {
		s.WriteString(col)
		padding := f.lengths[i] - len(col) + 1
		if padding < 1 {
			padding = 1
		}
		for i := 0; i < padding; i++ {
			s.WriteString(" ")
		}
	}
	return s.String()
}

// FormatRows automatically computes spacing and pretty-prints all the rows.
func (f *TextFormatter) FormatRows(rows [][]string) []string {
	var output []string
	f.setSpacingFromRows(rows)
	for _, row := range rows {
		output = append(output, f.formatRow(row))
	}
	return output
}

// FormatIPRange formats a slice of IP ranges for pretty-printing.
func FormatIPRange(ipRanges []*crimson.IPRange,
	format FormatType, skipHeader bool) ([]string, error) {
	var formatter Formatter

	switch format {
	case jsonFormat:
		jsonBytes, err := json.MarshalIndent(ipRanges, "", "  ")
		if err != nil {
			return []string{}, err
		}
		return []string{string(jsonBytes)}, nil
	case textFormat:
		formatter = &TextFormatter{}
	case csvFormat:
		formatter = &CSVFormatter{}
	case dhcpFormat:
		panic(fmt.Errorf("dhcp format is not supported for VLANs"))
	default:
		panic(fmt.Errorf("Unknown formatter: %v", formatter))
	}
	rows := [][]string{}
	if !skipHeader {
		rows = append(rows, []string{"site", "vlan ID", "Start IP", "End IP", "vlan alias"})
	}
	for _, ipRange := range ipRanges {
		rows = append(rows, []string{
			fmt.Sprintf("%s", ipRange.Site),
			fmt.Sprintf("%d", ipRange.VlanId),
			fmt.Sprintf("%s", ipRange.StartIp),
			fmt.Sprintf("%s", ipRange.EndIp),
			fmt.Sprintf("%s", ipRange.VlanAlias),
		})
	}
	return formatter.FormatRows(rows), nil
}

// PrintIPRange pretty-prints a slice of IP ranges.
func PrintIPRange(ipRanges []*crimson.IPRange, format FormatType, skipHeader bool) {
	lines, err := FormatIPRange(ipRanges, format, skipHeader)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s", err)
		return
	}
	for _, s := range lines {
		fmt.Println(s)
	}
}

func formatDhcpHostList(hosts []*crimson.Host) (out []string) {
	for _, host := range hosts {
		out = append(out, fmt.Sprintf(`host %s { hardware ethernet %s; fixed-address %s; ddns-hostname "%s"; option host-name "%s"; }`,
			host.Hostname, host.MacAddr, host.Ip, host.Hostname, host.Hostname))
	}
	return
}

// FormatHostList formats a list of hosts for pretty-printing.
func FormatHostList(
	hostList *crimson.HostList,
	format FormatType, skipHeader bool) ([]string, error) {
	var formatter Formatter

	switch format {
	case jsonFormat:
		jsonBytes, err := json.MarshalIndent(hostList.Hosts, "", "  ")
		if err != nil {
			return []string{}, err
		}
		return []string{string(jsonBytes)}, nil
	case textFormat:
		formatter = &TextFormatter{}
	case csvFormat:
		formatter = &CSVFormatter{}
	case dhcpFormat:
		return formatDhcpHostList(hostList.Hosts), nil
	default:
		panic(fmt.Errorf("Unknown formatter: %v", formatter))
	}
	rows := [][]string{}
	if !skipHeader {
		rows = append(rows, []string{"site", "hostname", "mac", "ip", "boot_class"})
	}
	for _, host := range hostList.Hosts {
		rows = append(rows, []string{
			fmt.Sprintf("%s", host.Site),
			fmt.Sprintf("%s", host.Hostname),
			fmt.Sprintf("%s", host.MacAddr),
			fmt.Sprintf("%s", host.Ip),
			fmt.Sprintf("%s", host.BootClass),
		})
	}
	return formatter.FormatRows(rows), nil
}

// PrintHostList pretty-prints a list of hosts.
func PrintHostList(hostList *crimson.HostList, format FormatType, skipHeader bool) {
	lines, err := FormatHostList(hostList, format, skipHeader)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ERROR: %s", err)
		return
	}
	for _, s := range lines {
		fmt.Println(s)
	}
}

// CheckDuplicateHosts does quick local sanity checks: hosts must have
// distinct hostnames, IPs and MAC addresses per each site.
func CheckDuplicateHosts(hostList *crimson.HostList) []error {
	hostnames := make(map[string]map[string]*crimson.Host)
	macs := make(map[string]map[string]*crimson.Host)
	ips := make(map[string]map[string]*crimson.Host)

	var errs []error

	for _, h := range hostList.Hosts {
		if h.Site == "" || h.Hostname == "" || h.MacAddr == "" || h.Ip == "" {
			errs = append(errs, fmt.Errorf("At least one of the required fields "+
				"(site, hostname, MAC, IP) is missing in host:\n  %s", h.String()))
			continue
		}

		if _, ok := hostnames[h.Site]; !ok {
			hostnames[h.Site] = make(map[string]*crimson.Host)
		}
		if _, ok := macs[h.Site]; !ok {
			macs[h.Site] = make(map[string]*crimson.Host)
		}
		if _, ok := ips[h.Site]; !ok {
			ips[h.Site] = make(map[string]*crimson.Host)
		}

		if h2, ok := hostnames[h.Site][h.Hostname]; !ok {
			hostnames[h.Site][h.Hostname] = h
		} else {
			errs = append(errs, fmt.Errorf("Duplicate hostname in:\n  %s\n, "+
				"already present in:\n  %s", h.String(), h2.String()))
		}

		if h2, ok := macs[h.Site][h.MacAddr]; !ok {
			macs[h.Site][h.MacAddr] = h
		} else {
			errs = append(errs, fmt.Errorf("Duplicate MAC address in:\n  %s\n, "+
				"already present in:\n  %s", h.String(), h2.String()))
		}

		if h2, ok := ips[h.Site][h.Ip]; !ok {
			ips[h.Site][h.Ip] = h
		} else {
			errs = append(errs, fmt.Errorf("Duplicate IP in\n  %s\n, "+
				"already present in:\n  %s", h.String(), h2.String()))
		}
	}
	return errs
}
