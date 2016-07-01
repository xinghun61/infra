// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"encoding/csv"
	"fmt"
	"io"
	"net"

	crimson "infra/crimson/proto"
)

// ReadCSVHostFile reads site, hostname, mac, ip and boot_class (in that order)
func ReadCSVHostFile(file io.Reader) (*crimson.HostList, error) {
	r := csv.NewReader(file)

	hostList := &crimson.HostList{}

	for {
		record, err := r.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		// Check we have enough values + their structure is correct.
		if len(record) < 4 || 5 < len(record) {
			return nil, fmt.Errorf(
				"Rows must contain 4 or 5 values, found one with %d: %s",
				len(record), record)
		}
		site := record[0]
		hostname := record[1]
		macAddr := record[2]
		_, err = net.ParseMAC(macAddr)
		if err != nil {
			return nil, fmt.Errorf("Invalid mac address found: %s", macAddr)
		}
		ip := record[3]
		parsedIP := net.ParseIP(ip)
		if parsedIP == nil {
			return nil, fmt.Errorf("Invalid IP address found: %s", ip)
		}
		bootClass := ""
		if len(record) == 5 {
			bootClass = record[4]
		}

		hostList.Hosts = append(hostList.Hosts,
			&crimson.Host{
				Site:      site,
				Hostname:  hostname,
				MacAddr:   macAddr,
				Ip:        ip,
				BootClass: bootClass})
	}
	return hostList, nil
}
