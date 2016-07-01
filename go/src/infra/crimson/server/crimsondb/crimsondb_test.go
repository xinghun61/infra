// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crimsondb

import (
	"database/sql/driver"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
	"infra/crimson/server/sqlmock"
)

func TestMacAddrStringToHexString(t *testing.T) {
	t.Parallel()
	Convey("MacAddrStringToHexString works", t, func() {
		Convey("on 00:00:00:00:00:00", func() {
			addr, err := MacAddrStringToHexString("00:00:00:00:00:00")
			So(err, ShouldBeNil)
			So(addr, ShouldEqual, "0x000000000000")
		})
		Convey("on 01:23:45:67:89:ab", func() {
			addr, err := MacAddrStringToHexString("01:23:45:67:89:ab")
			So(err, ShouldBeNil)
			So(addr, ShouldEqual, "0x0123456789ab")
		})
	})

	Convey("MacAddrStringToHexString returns an error", t, func() {
		Convey("on empty string", func() {
			_, err := MacAddrStringToHexString("")
			So(err, ShouldNotBeNil)
		})
		Convey("on 000000000000", func() {
			_, err := MacAddrStringToHexString("000000000000")
			So(err, ShouldNotBeNil)
		})
		Convey("on 'deadmeat'", func() {
			_, err := MacAddrStringToHexString("deadmeat")
			So(err, ShouldNotBeNil)
		})
	})
}

func TestHexStringToHardwareAddr(t *testing.T) {
	t.Parallel()

	Convey("HexStringToHardwareAddr works", t, func() {
		Convey("on 0x000000000000", func() {
			hw, err := HexStringToHardwareAddr("0x000000000000")
			So(err, ShouldBeNil)
			So(hw.String(), ShouldEqual, "00:00:00:00:00:00")
		})
		Convey("on 0x0123456789ab", func() {
			hw, err := HexStringToHardwareAddr("0x0123456789ab")
			So(err, ShouldBeNil)
			So(hw.String(), ShouldEqual, "01:23:45:67:89:ab")
		})
	})

	Convey("HexStringToHardwareAddr returns an error", t, func() {
		Convey("on empty string", func() {
			_, err := HexStringToHardwareAddr("")
			So(err, ShouldNotBeNil)
		})
		Convey("on 000000000000", func() {
			_, err := HexStringToHardwareAddr("000000000000")
			So(err, ShouldNotBeNil)
		})
		Convey("on '0xdeaddeadmeat'", func() {
			_, err := HexStringToHardwareAddr("0xdeaddeadmeat")
			So(err, ShouldNotBeNil)
		})
		Convey("on 'Aa000000000000'", func() {
			_, err := HexStringToHardwareAddr("Aa000000000000")
			So(err, ShouldNotBeNil)
		})
	})
}

func TestIPStringToHexString(t *testing.T) {
	t.Parallel()
	Convey("IPStringToHexString works", t, func() {
		Convey("on 192.168.0.1", func() {
			hexString, err := IPStringToHexString("192.168.0.1")
			expected := "0xc0a80001"
			So(hexString, ShouldEqual, expected)
			So(err, ShouldBeNil)
		})

		Convey("on 0.0.0.0", func() {
			hexString, err := IPStringToHexString("0.0.0.0")
			expected := "0x00000000"
			So(hexString, ShouldEqual, expected)
			So(err, ShouldBeNil)
		})
	})

	Convey("IPStringToHexString returns an error", t, func() {
		Convey("on empty string", func() {
			hexString, err := IPStringToHexString("")
			So(hexString, ShouldEqual, "")
			So(err, ShouldNotEqual, nil)
		})

		Convey("on non-numerical string with dots", func() {
			hexString, err := IPStringToHexString("ah.ah.ah.ah")
			So(hexString, ShouldEqual, "")
			So(err, ShouldNotEqual, nil)
		})

		Convey("on non-numerical string", func() {
			hexString, err := IPStringToHexString("aaaaaah")
			So(hexString, ShouldEqual, "")
			So(err, ShouldNotEqual, nil)
		})

		Convey("on '128.26.4'", func() {
			hexString, err := IPStringToHexString("128.26.4")
			So(hexString, ShouldEqual, "")
			So(err, ShouldNotEqual, nil)
		})
	})

}

func TestHexStringToIPString(t *testing.T) {
	t.Parallel()
	Convey("HexStringToIP works", t, func() {
		Convey("on 0x00000000", func() {
			ip, err := HexStringToIP("0x00000000")
			So(err, ShouldBeNil)
			expected := "0.0.0.0"
			So(ip.String(), ShouldEqual, expected)
		})
		Convey("on 0xc0a80001", func() {
			ip, err := HexStringToIP("0xc0a80001")
			So(err, ShouldBeNil)
			expected := "192.168.0.1"
			So(ip.String(), ShouldEqual, expected)
		})
		Convey("on 0XC0A80002", func() {
			ip, err := HexStringToIP("0XC0A80002")
			So(err, ShouldBeNil)
			expected := "192.168.0.2"
			So(ip.String(), ShouldEqual, expected)
		})
	})
	Convey("HexStringToIP returns an error", t, func() {
		Convey("on empty string", func() {
			ip, err := HexStringToIP("0XC0A80002")
			So(err, ShouldBeNil)
			expected := "192.168.0.2"
			So(ip.String(), ShouldEqual, expected)
		})
	})

}

func TestIPStringToHexAndBack(t *testing.T) {
	t.Parallel()
	// Check that function which are supposed to be exact inverse actually are.
	Convey("HexStringToIP and IPStringToHexString are inverse of each other",
		t, func() {
			Convey("on 135.45.1.84", func() {
				ip1 := "135.45.1.84"
				value, err := IPStringToHexString(ip1)
				So(err, ShouldBeNil)
				ip2, err := HexStringToIP(value)
				So(err, ShouldBeNil)
				So(ip1, ShouldEqual, ip2.String())
			})

			Convey("on 1.2.3.4", func() {
				ip1 := "1.2.3.4"
				value, err := IPStringToHexString(ip1)
				So(err, ShouldBeNil)
				ip2, err := HexStringToIP(value)
				So(err, ShouldBeNil)
				So(ip1, ShouldEqual, ip2.String())
			})

			Convey("on 255.255.255.255", func() {
				ip1 := "255.255.255.255"
				value, err := IPStringToHexString(ip1)
				So(err, ShouldBeNil)
				ip2, err := HexStringToIP(value)
				So(err, ShouldBeNil)
				So(ip1, ShouldEqual, ip2.String())
			})
		})
}

func TestSelectIPRange(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	db, conn := sqlmock.NewMockDB()
	ctx = UseDB(ctx, db)

	Convey("SelectIPRange", t, func() {
		Convey("without parameter", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := "SELECT site, vlan, start_ip, end_ip FROM ip_range"
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{})
			})
		})

		Convey("with only vlan", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Vlan: "xyz"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE vlan=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"xyz"})
			})
		})

		Convey("with only site", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Site: "abc"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE site=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"abc"})
			})
		})

		Convey("with vlan and site", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Site: "abc", Vlan: "xyz"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE site=?\n" +
					"AND vlan=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"abc", "xyz"})
			})
		})

		Convey("with vlan and limit", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Limit: 15, Vlan: "xyz"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE vlan=?\n" +
					"LIMIT ?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"xyz", int64(15)})
			})
		})

		Convey("with only limit", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Limit: 14})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"LIMIT ?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{int64(14)})
			})
		})

		Convey("with ip filtering", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Ip: "192.168.1.0"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE start_ip<=? AND ?<=end_ip")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble,
					[]driver.Value{"0xc0a80100", "0xc0a80100"})
			})
		})

		Convey("with site and ip filtering", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Site: "foo", Ip: "192.168.1.0"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
					"WHERE site=?\nAND start_ip<=? AND ?<=end_ip")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble,
					[]driver.Value{"foo", "0xc0a80100", "0xc0a80100"})
			})
		})
	})
}

func TestInsertIPRange(t *testing.T) {
	t.Parallel()
	Convey("InsertIPRange", t, func() {
		ctx := context.Background()
		db, conn := sqlmock.NewMockDB()
		ctx = UseDB(ctx, db)

		Convey("without an overlapping range, calls INSERT.", func() {
			InsertIPRange(ctx,
				&crimson.IPRange{
					Site:    "site0",
					Vlan:    "vlan0",
					StartIp: "1.2.3.4",
					EndIp:   "1.2.3.20"})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("LOCK TABLES ip_range WRITE")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
				"WHERE site=? AND start_ip<=? AND end_ip>=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"0x01020314",
					"0x01020304"})

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("INSERT INTO ip_range (site, vlan, start_ip, end_ip)\n" +
				"VALUES (?, ?, ?, ?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"vlan0",
					"0x01020304",
					"0x01020314"})
		})

		Convey("with an overlapping range, does not call INSERT.", func() {
			So(conn.PushRows([][]driver.Value{{"site0", "vlan0", "1.2.3.4", "1.2.3.20"}}),
				ShouldBeNil)

			InsertIPRange(ctx,
				&crimson.IPRange{
					Site:    "site0",
					Vlan:    "vlan0",
					StartIp: "1.2.3.4",
					EndIp:   "1.2.3.20"})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("LOCK TABLES ip_range WRITE")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("SELECT site, vlan, start_ip, end_ip FROM ip_range\n" +
				"WHERE site=? AND start_ip<=? AND end_ip>=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"0x01020314",
					"0x01020304"})

			query, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})
	})
}

func TestInsertHost(t *testing.T) {
	t.Parallel()
	Convey("InsertHost", t, func() {
		ctx := context.Background()
		db, conn := sqlmock.NewMockDB()
		ctx = UseDB(ctx, db)

		Convey("with one host, generates the correct queries.", func() {
			err := InsertHost(ctx,
				&crimson.HostList{
					Hosts: []*crimson.Host{{
						Site:      "site0",
						Hostname:  "hostname0",
						MacAddr:   "01:23:45:67:89:ab",
						Ip:        "1.2.3.20",
						BootClass: "linux"}}})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("INSERT INTO host (site, hostname, mac_addr, ip, boot_class) " +
				"VALUES (?, ?, ?, ?, ?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"hostname0",
					"0x0123456789ab",
					"0x01020314",
					"linux"})
		})
	})
}

func TestSelectHost(t *testing.T) {
	t.Parallel()
	Convey("SelectHost", t, func() {
		ctx := context.Background()
		db, conn := sqlmock.NewMockDB()
		ctx = UseDB(ctx, db)

		Convey("given a site generates a correct query", func() {
			_, err := SelectHost(ctx,
				&crimson.HostQuery{
					Site: "site0",
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nWHERE site=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"site0"})
		})

		Convey("given a site and a boot class generates a correct query", func() {
			_, err := SelectHost(ctx,
				&crimson.HostQuery{
					Site:      "site0",
					BootClass: "cls",
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nWHERE site=?\nAND boot_class=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"site0", "cls"})
		})

		Convey("with all filters generates a correct query", func() {
			_, err := SelectHost(ctx,
				&crimson.HostQuery{
					Site:      "site0",
					Hostname:  "hostname0",
					MacAddr:   "01:23:45:67:89:ab",
					Ip:        "1.23.45.67",
					BootClass: "cls",
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nWHERE site=?\nAND hostname=?\nAND mac_addr=?\nAND ip=?" +
				"\nAND boot_class=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"site0", "hostname0",
				"0x0123456789ab", "0x01172d43", "cls"})
		})

		Convey("given a boot class and a limit generates a correct query", func() {
			_, err := SelectHost(ctx,
				&crimson.HostQuery{
					Limit:     10,
					BootClass: "cls",
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nWHERE boot_class=?\nLIMIT ?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"cls", int64(10)})
		})

		Convey("given a limit generates a correct query", func() {
			_, err := SelectHost(ctx,
				&crimson.HostQuery{
					Limit: 10})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nLIMIT ?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{int64(10)})
		})

		Convey("parses resulting row properly", func() {
			So(conn.PushRows([][]driver.Value{
				{"site0", "hostname0", "0x0123456789ab", "0x01234567", "linux"}}),
				ShouldBeNil)
			hostList, err := SelectHost(ctx,
				&crimson.HostQuery{
					Limit: 10})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nLIMIT ?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{int64(10)})

			So(hostList.Hosts[0], ShouldResemble,
				&crimson.Host{
					Site:      "site0",
					Hostname:  "hostname0",
					MacAddr:   "01:23:45:67:89:ab",
					Ip:        "1.35.69.103",
					BootClass: "linux"})
		})
		Convey("parses resulting row with NULL properly", func() {
			So(conn.PushRows([][]driver.Value{
				{"site0", "hostname0", "0x0123456789ab", "0x01234567", nil}}),
				ShouldBeNil)
			hostList, err := SelectHost(ctx,
				&crimson.HostQuery{
					Limit: 10})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("SELECT site, hostname, mac_addr, ip, boot_class " +
				"FROM host\nLIMIT ?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{int64(10)})

			So(hostList.Hosts[0], ShouldResemble,
				&crimson.Host{
					Site:      "site0",
					Hostname:  "hostname0",
					MacAddr:   "01:23:45:67:89:ab",
					Ip:        "1.35.69.103",
					BootClass: ""})
		})
	})
}

func TestDeleteHost(t *testing.T) {
	t.Parallel()
	Convey("DeleteHost", t, func() {
		ctx := context.Background()
		db, conn := sqlmock.NewMockDB()
		ctx = UseDB(ctx, db)

		Convey("given one hostname generates a correct query", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{{Hostname: "host0"}},
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("DELETE FROM host\nWHERE (hostname=?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"host0"})
		})

		Convey("given two hostnames generates a correct query", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{
						{Hostname: "host0"},
						{Hostname: "host1"}},
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("DELETE FROM host\nWHERE (hostname=?)\nOR (hostname=?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"host0", "host1"})
		})

		Convey("given a hostname and a mac generates a correct query", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{
						{Hostname: "host0", MacAddr: "01:23:45:67:89:ab"}},
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("DELETE FROM host\nWHERE (hostname=? AND mac_addr=?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"host0", "0x0123456789ab"})
		})

		Convey("given two (hostname, mac) generates a correct query", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{
						{Hostname: "host0", MacAddr: "01:23:45:67:89:ab"},
						{Hostname: "host1", MacAddr: "01:23:45:67:89:ac"}},
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("DELETE FROM host\nWHERE (hostname=? AND mac_addr=?)\n" +
				"OR (hostname=? AND mac_addr=?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{"host0", "0x0123456789ab", "host1", "0x0123456789ac"})
		})

		Convey("given a hostname then a mac generates a correct query", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{
						{Hostname: "host0"},
						{MacAddr: "01:23:45:67:89:ab"}},
				})

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("DELETE FROM host\nWHERE (hostname=?)\nOR (mac_addr=?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble, []driver.Value{"host0", "0x0123456789ab"})
		})

		Convey("given a blank input returns an error", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{{}},
				})
			So(err, ShouldNotBeNil)
			_, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("given an invalid mac returns an error", func() {
			err := DeleteHost(ctx,
				&crimson.HostDeleteList{
					Hosts: []*crimson.HostDelete{
						{Hostname: "host0"},
						{MacAddr: "xx:23:45:67:89:ab"}},
				})
			So(err, ShouldNotBeNil)
			_, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})
	})
}
