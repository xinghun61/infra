// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net"
	"regexp"
	"strings"

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
	vlan   string
	suffix string
	subnet net.IPNet
	pools  []Pool
}

// IPRanges converts a Subnet into an array of IPRange.
func (subnet *Subnet) IPRanges(site string) []*crimson.IPRange {
	ipRange := []*crimson.IPRange{}
	for _, pool := range subnet.pools {
		ipRange = append(ipRange, &crimson.IPRange{
			Vlan:    subnet.vlan,
			Site:    site,
			StartIp: pool.startIP,
			EndIp:   pool.endIP,
		})
	}
	return ipRange
}

// ReadDhcpdConfFile reads the subnet sections in a dhcpd.conf file.
func ReadDhcpdConfFile(file io.Reader) ([]Subnet, error) {
	// TODO(pgervais): test this function
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
			subnet := readSubnetSection(line, scanner)
			if names.vlanName != "" {
				subnet.vlan = names.vlanName
				subnet.suffix = names.vlanSuffix
				names = vlanNames{}
			}
			subnets = append(subnets, subnet)
		}
	}
	return subnets, nil
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

func readSubnetSection(firstLine string, scanner *bufio.Scanner) Subnet {
	// TODO(pgervais) Double-Check firstLine starts with 'subnet'
	subnet := Subnet{}

	fields := strings.Fields(firstLine)
	for ind, field := range fields {
		switch field {
		case "subnet":
			subnet.subnet.IP = net.ParseIP(fields[ind+1])
		case "netmask":
			subnet.subnet.Mask = parseIPMask(fields[ind+1])
		}
	}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "pool") {
			pool := readPoolSection(line, scanner)
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
	return subnet
}

func readPoolSection(firstLine string, scanner *bufio.Scanner) Pool {
	// TODO(pgervais): double-check firstLine starts with 'pool'
	pool := Pool{}
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "range") {
			line = strings.TrimRight(line, ";")
			fields := strings.Fields(line)
			pool.startIP = fields[1]
			pool.endIP = fields[2]
		}
		if line == "}" {
			break
		}
	}
	return pool
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

// PrintIPRange pretty-prints a slice of IP ranges.
func PrintIPRange(ipRanges []*crimson.IPRange) {
	fmt.Println("site \tvlan \t IP range")
	for _, ipRange := range ipRanges {
		fmt.Printf("%s \t %s \t%s-%s\n",
			ipRange.Site, ipRange.Vlan, ipRange.StartIp, ipRange.EndIp)
	}
}
