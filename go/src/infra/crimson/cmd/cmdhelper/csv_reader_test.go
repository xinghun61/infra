// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
)

func TestReadCSVHostFile(t *testing.T) {
	t.Parallel()
	Convey("Parsing a valid CSV file with five columns works", t, func() {
		r := strings.NewReader("site0,host0,01:23:45:67:89:ab,1.2.3.4,linux\n" +
			"site1,host1,01:23:45:67:89:ac,1.2.3.5,\n")
		hosts, err := ReadCSVHostFile(r)
		So(err, ShouldBeNil)
		So(hosts, ShouldResemble,
			&crimson.HostList{
				Hosts: []*crimson.Host{
					{Site: "site0",
						Hostname:  "host0",
						MacAddr:   "01:23:45:67:89:ab",
						Ip:        "1.2.3.4",
						BootClass: "linux"},
					{Site: "site1",
						Hostname:  "host1",
						MacAddr:   "01:23:45:67:89:ac",
						Ip:        "1.2.3.5",
						BootClass: ""},
				},
			})
	})

	Convey("Parsing a valid CSV file with four columns works", t, func() {
		r := strings.NewReader("site0,host0,01:23:45:67:89:ab,1.2.3.4\n" +
			"site1,host1,01:23:45:67:89:ac,1.2.3.5\n")
		hosts, err := ReadCSVHostFile(r)
		So(err, ShouldBeNil)
		So(hosts, ShouldResemble,
			&crimson.HostList{
				Hosts: []*crimson.Host{
					{Site: "site0",
						Hostname:  "host0",
						MacAddr:   "01:23:45:67:89:ab",
						Ip:        "1.2.3.4",
						BootClass: ""},
					{Site: "site1",
						Hostname:  "host1",
						MacAddr:   "01:23:45:67:89:ac",
						Ip:        "1.2.3.5",
						BootClass: ""},
				},
			})
	})

	Convey("Parsing an empty CSV file works", t, func() {
		r := strings.NewReader("")
		hosts, err := ReadCSVHostFile(r)
		So(err, ShouldBeNil)
		So(hosts, ShouldResemble, &crimson.HostList{})
	})

	Convey("Parsing a CSV file with invalid MAC triggers an error", t, func() {
		r := strings.NewReader("site0,host0,01:23:xx:67:89:ab,1.2.3.4,linux")
		hosts, err := ReadCSVHostFile(r)
		So(err, ShouldNotBeNil)
		So(hosts, ShouldBeNil)
	})

	Convey("Parsing a CSV file with invalid IP triggers an error", t, func() {
		r := strings.NewReader("site0,host0,01:23:45:67:89:ab,1.2.3.400,linux")
		hosts, err := ReadCSVHostFile(r)
		So(err, ShouldNotBeNil)
		So(hosts, ShouldBeNil)
	})
}
