// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
)

func TestReadDhcpFile(t *testing.T) {
	t.Parallel()
	Convey("Reading dhcp hosts file", t, func() {
		Convey("works for a valid file", func() {
			fileName := filepath.Join("testdata", "dhcp-good.conf")

			site := "test-site"
			bootClass := "test-class"
			expected := crimson.HostList{Hosts: []*crimson.Host{
				{
					Site:      site,
					Hostname:  "testhost-1",
					MacAddr:   "de:ed:be:ef:f0:0d",
					Ip:        "192.168.1.1",
					BootClass: bootClass,
				},
				{
					Site:      site,
					Hostname:  "testhost-2",
					MacAddr:   "de:ed:be:ef:f0:0e",
					Ip:        "192.168.1.2",
					BootClass: bootClass,
				},
			}}

			hosts, err := readDhcpFileByName(fileName, bootClass, site)
			So(err, ShouldBeNil)
			So(hosts, ShouldResemble, expected)
		})

		Convey("errors on a nonexistent file", func() {
			_, err := readDhcpFileByName("nonexistentfile", "boot", "site")
			So(err, ShouldNotBeNil)
		})
	})
}
