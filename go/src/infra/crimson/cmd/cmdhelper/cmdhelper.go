// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"regexp"
	"strings"

	"github.com/luci/luci-go/common/flag/flagenum"

	crimson "infra/crimson/proto"
)

var vlanRe = regexp.MustCompile(
	`^ *# *@(vlan-name|vlan-suffix) *: *([a-zA-Z0-9/@._-]+) *$`)

// Pool represents a pool section in a dhcpd.conf file.
type Pool struct {
	startIP string
	endIP   string
}

// Subnet represents a subnet section in a dhcpd.conf file.
type Subnet struct {
	vlanID   uint32
	vlanName string
	suffix   string
	subnet   net.IPNet
	pools    []Pool
}

// IPRanges converts a Subnet into an array of IPRange.
func (subnet *Subnet) IPRanges(site string) []*crimson.IPRange {
	ipRange := []*crimson.IPRange{}
	for _, pool := range subnet.pools {
		ipRange = append(ipRange, &crimson.IPRange{
			Site:      site,
			VlanId:    subnet.vlanID,
			StartIp:   pool.startIP,
			EndIp:     pool.endIP,
			VlanAlias: subnet.vlanName,
		})
	}
	return ipRange
}

// ReadDhcpdConfFile reads the subnet sections in a dhcpd.conf file.
func ReadDhcpdConfFile(file io.Reader, site string) ([]*crimson.IPRange, error) {
	var subnets []Subnet

	scanner := bufio.NewScanner(file)

	names := vlanNames{}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		switch {
		case len(line) == 0:
			continue
		case strings.HasPrefix(line, "#"):
			// Ignore errors here, it's fine.
			names.getVlanFromComment(line)
		case strings.HasPrefix(line, "subnet"):
			subnet, err := readSubnetSection(line, scanner)
			if err != nil {
				return nil, err
			}
			if names.vlanName != "" {
				subnet.vlanName = names.vlanName
				subnet.suffix = names.vlanSuffix
				names = vlanNames{}
			}
			subnets = append(subnets, subnet)
		}
	}

	var ranges []*crimson.IPRange
	for _, subnet := range subnets {
		ranges = append(ranges, subnet.IPRanges(site)...)
	}

	return ranges, nil
}

type vlanNames struct {
	vlanName   string
	vlanSuffix string
}

func (names *vlanNames) getVlanFromComment(line string) error {
	// In the name, avoid characters usually treated specially somehow:
	// ~'"!#^&$%*?\()[]{}|<>;:+
	parts := vlanRe.FindStringSubmatch(line)

	if parts == nil {
		return fmt.Errorf("No crdb comment found in string.")
	}

	if parts[1] == "vlan-name" {
		names.vlanName = parts[2]
	} else {
		names.vlanSuffix = parts[2]
	}
	return nil
}

func readSubnetSection(firstLine string, scanner *bufio.Scanner) (Subnet, error) {
	// TODO(pgervais) Double-Check firstLine starts with 'subnet'
	subnet := Subnet{}

	fields := strings.Fields(firstLine)
	for ind, field := range fields {
		switch field {
		case "subnet":
			subnet.subnet.IP = net.ParseIP(fields[ind+1])
			if subnet.subnet.IP == nil {
				return subnet, fmt.Errorf("Failed to parse subnet IP in %s", firstLine)
			}
		case "netmask":
			subnet.subnet.Mask = parseIPMask(fields[ind+1])
			if subnet.subnet.Mask == nil {
				return subnet, fmt.Errorf("Failed to parse subnet mask in %s", firstLine)
			}
		}
	}
	// Convention: 3rd byte in IPv4 is the vlan ID. IPv4 can be encoded as IPv6.
	// TODO(sergeyberezin): this is Chrome Infra specific, and should be
	// moved to customization scripts.
	ip := subnet.subnet.IP
	subnet.vlanID = uint32(ip[len(ip)-2])

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "pool") {
			pool, err := readPoolSection(line, scanner)
			if err != nil {
				return subnet, err
			}
			subnet.pools = append(subnet.pools, pool)
		}
		if line == "}" {
			break
		}
	}

	if len(subnet.pools) == 0 {
		startIP, endIP := subnetExtremeIPs(subnet.subnet)
		pool := Pool{}
		pool.startIP = startIP.String()
		pool.endIP = endIP.String()
		subnet.pools = append(subnet.pools, pool)
	}
	return subnet, nil
}

func readPoolSection(firstLine string, scanner *bufio.Scanner) (Pool, error) {
	// TODO(pgervais): double-check firstLine starts with 'pool'
	pool := Pool{}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "range") {
			line = strings.TrimRight(line, ";")
			fields := strings.Fields(line)
			if len(fields) < 2 {
				return pool, fmt.Errorf("Failed to parse pool range: %s", line)
			}
			pool.startIP = fields[1]
			pool.endIP = fields[2]
		}
		if line == "}" {
			break
		}
	}
	return pool, nil
}

func subnetExtremeIPs(subnet net.IPNet) (net.IP, net.IP) {
	// This function works with IPv4 and IPv6 addresses and masks.
	startIP := subnet.IP.Mask(subnet.Mask)

	// Adapted from https://golang.org/src/net/ip.go?s=5955:5988#L236
	mask := subnet.Mask
	ip := subnet.IP
	if len(mask) == net.IPv6len && len(ip) == net.IPv4len && allFF(mask[:12]) {
		mask = mask[12:]
	}

	if len(mask) == net.IPv4len && len(ip) == net.IPv6len && isIPv4(ip) {
		ip = ip[12:]
	}
	n := len(ip)
	if n != len(mask) {
		return startIP, nil
	}
	endIP := make(net.IP, n)
	for i := 0; i < n; i++ {
		endIP[i] = ip[i] | (^mask[i])
	}
	return startIP, endIP
}

// Parses an IP address as a mask, valid for v4 and v6
func parseIPMask(s string) net.IPMask {
	ip := net.ParseIP(s)
	if isIPv4(ip) {
		return net.IPv4Mask(ip[len(ip)-4], ip[len(ip)-3], ip[len(ip)-2], ip[len(ip)-1])
	}
	return net.IPMask(ip)
}

// Adapted from https://golang.org/src/net/ip.go
func allFF(b []byte) bool {
	for _, c := range b {
		if c != 0xff {
			return false
		}
	}
	return true
}

func isIPv4(ip net.IP) bool {
	var v4InV6Prefix = []byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff}
	return bytes.Equal(ip[:12], v4InV6Prefix)
}

// Formatter formats tables for printing according to -format flag.
type Formatter interface {
	// FormatRows formats rows of a table as strings for pretty-printing.
	FormatRows(rows [][]string) []string
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

// FormatType is the type for enum values for the -format flag.
type FormatType string

var _ flag.Value = (*FormatType)(nil)

const (
	textFormat = FormatType("text")
	csvFormat  = FormatType("csv")
	jsonFormat = FormatType("json")
	// DefaultFormat is the default value to use for FormatType.
	DefaultFormat = textFormat
)

// FormatTypeEnum is the value type for the -format flag.
var FormatTypeEnum = flagenum.Enum{
	"text": textFormat,
	"csv":  csvFormat,
	"json": jsonFormat,
}

func (ft *FormatType) String() string {
	return FormatTypeEnum.FlagString(*ft)
}

// Set implements flag.Value
func (ft *FormatType) Set(v string) error {
	return FormatTypeEnum.FlagSet(ft, v)
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
