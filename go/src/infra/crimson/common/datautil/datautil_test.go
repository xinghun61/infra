// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package datautil

import (
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
)

func TestFormatter(t *testing.T) {
	t.Parallel()
	Convey("Formatter implementations work", t, func() {
		rows := [][]string{
			{"Col 1", "Long name col 2"},
			{"longvalue1", "v2"},
		}
		Convey("as CSVFormatter", func() {
			csvf := CSVFormatter{}
			So(csvf.FormatRows(rows), ShouldResemble, []string{
				"Col 1,Long name col 2",
				"longvalue1,v2",
			})
		})

		Convey("as TextFormatter", func() {
			Convey("for uniform table", func() {
				textf := TextFormatter{}
				So(textf.FormatRows(rows), ShouldResemble, []string{
					"Col 1      Long name col 2 ",
					"longvalue1 v2              ",
				})
			})
			Convey("for table with variable number of columns", func() {
				rows = append(rows, []string{"col1", "col2", "extra col"})
				textf := TextFormatter{}
				So(textf.FormatRows(rows), ShouldResemble, []string{
					"Col 1      Long name col 2 ",
					"longvalue1 v2              ",
					"col1       col2            extra col ",
				})
			})
		})
	})
}

func TestFormatIPRange(t *testing.T) {
	t.Parallel()

	Convey("FormatIPRange works", t, func() {
		ipRanges := []*crimson.IPRange{
			{
				Site:      "site1",
				VlanId:    123,
				VlanAlias: "vlan1",
				StartIp:   "123.234.0.1",
				EndIp:     "123.234.1.244",
			},
			{
				Site:      "site2",
				VlanId:    124,
				VlanAlias: "vlan2",
				StartIp:   "125.200.0.1",
				EndIp:     "126.233.1.255",
			},
		}

		Convey("for text format", func() {
			lines, err := FormatIPRange(ipRanges, textFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site  vlan ID Start IP    End IP        vlan alias ",
				"site1 123     123.234.0.1 123.234.1.244 vlan1      ",
				"site2 124     125.200.0.1 126.233.1.255 vlan2      ",
			})
		})

		Convey("for CSV format", func() {
			lines, err := FormatIPRange(ipRanges, csvFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site,vlan ID,Start IP,End IP,vlan alias",
				"site1,123,123.234.0.1,123.234.1.244,vlan1",
				"site2,124,125.200.0.1,126.233.1.255,vlan2",
			})
		})

		Convey("for CSV format without header", func() {
			lines, err := FormatIPRange(ipRanges, csvFormat, true)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site1,123,123.234.0.1,123.234.1.244,vlan1",
				"site2,124,125.200.0.1,126.233.1.255,vlan2",
			})
		})

		Convey("for CSV format with ',' in values", func() {
			ipRanges = append(ipRanges, &crimson.IPRange{
				Site:      "site,3",
				VlanId:    8,
				VlanAlias: "vl,an3",
				StartIp:   "1",
				EndIp:     "2",
			})
			lines, err := FormatIPRange(ipRanges, csvFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site,vlan ID,Start IP,End IP,vlan alias",
				"site1,123,123.234.0.1,123.234.1.244,vlan1",
				"site2,124,125.200.0.1,126.233.1.255,vlan2",
				"\"site,3\",8,1,2,\"vl,an3\"",
			})
		})

		Convey("for JSON format", func() {
			lines, err := FormatIPRange(ipRanges, jsonFormat, false)
			So(err, ShouldBeNil)
			So(len(lines), ShouldEqual, 1)
			var outIPRanges []*crimson.IPRange
			json.Unmarshal([]byte(lines[0]), &outIPRanges)
			So(outIPRanges, ShouldResemble, ipRanges)
		})
	})
}

func TestFormatHostList(t *testing.T) {
	t.Parallel()

	Convey("FormatHostList works", t, func() {
		hostList := &crimson.HostList{Hosts: []*crimson.Host{
			{
				Site:      "site1",
				Hostname:  "host1",
				MacAddr:   "de:ed:be:ef:f0:0d",
				Ip:        "127.0.0.1",
				BootClass: "boot1",
			},
			{
				Site:      "site2",
				Hostname:  "host2",
				MacAddr:   "ba:dc:0f:ee:f0:0d",
				Ip:        "127.0.0.2",
				BootClass: "boot2",
			},
		}}

		Convey("for CSV format", func() {
			expected := []string{
				"site,hostname,mac,ip,boot_class",
				"site1,host1,de:ed:be:ef:f0:0d,127.0.0.1,boot1",
				"site2,host2,ba:dc:0f:ee:f0:0d,127.0.0.2,boot2",
			}
			lines, err := FormatHostList(hostList, csvFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, expected)

			lines, err = FormatHostList(hostList, csvFormat, true)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, expected[1:])
		})

		Convey("for text format", func() {
			expected := []string{
				"site  hostname mac               ip        boot_class ",
				"site1 host1    de:ed:be:ef:f0:0d 127.0.0.1 boot1      ",
				"site2 host2    ba:dc:0f:ee:f0:0d 127.0.0.2 boot2      ",
			}
			lines, err := FormatHostList(hostList, textFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, expected)

			expected = []string{
				"site1 host1 de:ed:be:ef:f0:0d 127.0.0.1 boot1 ",
				"site2 host2 ba:dc:0f:ee:f0:0d 127.0.0.2 boot2 ",
			}
			lines, err = FormatHostList(hostList, textFormat, true)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, expected)
		})

		Convey("for JSON format", func() {
			lines, err := FormatHostList(hostList, jsonFormat, false)
			So(err, ShouldBeNil)
			So(len(lines), ShouldEqual, 1)
			var hosts []*crimson.Host
			json.Unmarshal([]byte(lines[0]), &hosts)
			So(hosts, ShouldResemble, hostList.Hosts)
		})

		Convey("for DHCP format", func() {
			lines, err := FormatHostList(hostList, dhcpFormat, false)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				`host host1 { hardware ethernet de:ed:be:ef:f0:0d; fixed-address 127.0.0.1; ddns-hostname "host1"; option host-name "host1"; }`,
				`host host2 { hardware ethernet ba:dc:0f:ee:f0:0d; fixed-address 127.0.0.2; ddns-hostname "host2"; option host-name "host2"; }`,
			})
		})
	})
}

func TestCheckDuplicateHosts(t *testing.T) {
	t.Parallel()

	Convey("CheckDuplicateHosts works", t, func() {
		hosts := &crimson.HostList{Hosts: []*crimson.Host{
			{
				Site:      "site1",
				MacAddr:   "mac1",
				Hostname:  "host1",
				Ip:        "IP1",
				BootClass: "boot1",
			},
			{
				Site:      "site2",
				MacAddr:   "mac2",
				Hostname:  "host2",
				Ip:        "IP2",
				BootClass: "boot2",
			},
		}}
		Convey("without duplicates", func() {
			So(len(CheckDuplicateHosts(hosts)), ShouldEqual, 0)
		})

		Convey("duplicate hosts in different sites are OK", func() {
			hosts.Hosts = append(hosts.Hosts, &crimson.Host{
				Site:      "site2",
				MacAddr:   "mac3",
				Hostname:  "host1",
				Ip:        "IP3",
				BootClass: "boot3",
			})
			So(len(CheckDuplicateHosts(hosts)), ShouldEqual, 0)
		})

		Convey("catches duplicate host", func() {
			hosts.Hosts = append(hosts.Hosts, &crimson.Host{
				Site:      "site1",
				MacAddr:   "mac3",
				Hostname:  "host1",
				Ip:        "IP3",
				BootClass: "boot3",
			})
			So(len(CheckDuplicateHosts(hosts)), ShouldEqual, 1)
		})

		Convey("catches duplicate MAC address", func() {
			hosts.Hosts = append(hosts.Hosts, &crimson.Host{
				Site:      "site1",
				MacAddr:   "mac1",
				Hostname:  "host3",
				Ip:        "IP3",
				BootClass: "boot3",
			})
			So(len(CheckDuplicateHosts(hosts)), ShouldEqual, 1)
		})

		Convey("catches duplicate IP", func() {
			hosts.Hosts = append(hosts.Hosts, &crimson.Host{
				Site:      "site2",
				MacAddr:   "mac3",
				Hostname:  "host3",
				Ip:        "IP2",
				BootClass: "boot3",
			})
			So(len(CheckDuplicateHosts(hosts)), ShouldEqual, 1)
		})
	})
}
