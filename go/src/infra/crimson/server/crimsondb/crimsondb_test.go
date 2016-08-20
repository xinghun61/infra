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
				expected := "SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan"
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{})
			})
		})

		Convey("with only vlan ID", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{VlanId: 42})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
					"WHERE vlan_id=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{int64(42)})
			})
		})

		Convey("with only vlan alias", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{VlanAlias: "xyz"})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
					"WHERE vlan_alias=?")
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
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
					"WHERE site=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"abc"})
			})
		})

		Convey("with vlan ID and site", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Site: "abc", VlanId: 42})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
					"WHERE site=?\n" +
					"AND vlan_id=?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{"abc", int64(42)})
			})
		})

		Convey("with vlan ID and limit", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Limit: 15, VlanId: 42})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
					"WHERE vlan_id=?\n" +
					"LIMIT ?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{int64(42), int64(15)})
			})
		})

		Convey("with only limit", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{Limit: 14})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
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
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
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
				expected := ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
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
			ierr := InsertIPRange(ctx,
				&crimson.IPRange{
					Site:      "site0",
					VlanId:    8,
					VlanAlias: "vlan0",
					StartIp:   "1.2.3.4",
					EndIp:     "1.2.3.20"})

			So(ierr, ShouldBeNil)

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("LOCK TABLES vlan WRITE")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
				"WHERE site=? AND start_ip<=? AND end_ip>=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"0x01020314",
					"0x01020304"})

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("INSERT INTO vlan (site, vlan_id, start_ip, end_ip, vlan_alias)\n" +
				"VALUES (?, ?, ?, ?, ?)")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					int64(8),
					"0x01020304",
					"0x01020314",
					"vlan0",
				})
			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("UNLOCK TABLES")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("with an overlapping range, does not call INSERT.", func() {
			So(conn.PushRows([][]driver.Value{{
				"site0", "08", "0x01020314", "0x01020304", "vlan0"}}),
				ShouldBeNil)

			ierr := InsertIPRange(ctx,
				&crimson.IPRange{
					Site:    "site0",
					VlanId:  8,
					StartIp: "1.2.3.4",
					EndIp:   "1.2.3.20"})

			So(ierr, ShouldNotBeNil)

			query, err := conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected := ("LOCK TABLES vlan WRITE")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("SELECT site, vlan_id, start_ip, end_ip, vlan_alias FROM vlan\n" +
				"WHERE site=? AND start_ip<=? AND end_ip>=?")
			So(query.Query, ShouldEqual, expected)
			So(query.Args, ShouldResemble,
				[]driver.Value{
					"site0",
					"0x01020314",
					"0x01020304"})

			query, err = conn.PopOldestQuery()
			So(err, ShouldBeNil)
			expected = ("UNLOCK TABLES")
			So(query.Query, ShouldEqual, expected)

			query, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("Invalid VLAN ID fails and does not call INSERT.", func() {
			err := InsertIPRange(ctx,
				&crimson.IPRange{
					Site:    "site0",
					VlanId:  0,
					StartIp: "1.2.3.4",
					EndIp:   "1.2.3.20"})
			So(err, ShouldNotBeNil)

			err = InsertIPRange(ctx,
				&crimson.IPRange{
					Site:    "site0",
					VlanId:  4097,
					StartIp: "1.2.3.4",
					EndIp:   "1.2.3.20"})
			So(err, ShouldNotBeNil)

			_, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

	})
}

func TestDeleteIPRange(t *testing.T) {
	t.Parallel()
	Convey("DeleteIPRange", t, func() {
		ctx := context.Background()
		db, conn := sqlmock.NewMockDB()
		ctx = UseDB(ctx, db)

		Convey("with valid arguments constructs expected query", func() {
			err := DeleteIPRange(ctx, &crimson.IPRangeDeleteList{
				Ranges: []*crimson.IPRangeDelete{
					{Site: "site1", VlanId: 1},
					{Site: "site2", VlanId: 2},
				}})
			So(err, ShouldBeNil)
			query, qErr := conn.PopOldestQuery()
			So(qErr, ShouldBeNil)
			expected := "DELETE FROM vlan\nWHERE (site=? AND vlan_id=?)\nOR (site=? AND vlan_id=?)"
			So(query.Query, ShouldEqual, expected)
			// driver.Value upconverts all int types to int64.
			So(query.Args, ShouldResemble, []driver.Value{"site1", int64(1), "site2", int64(2)})

			// No extra queries
			query, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("with empty list returns an error", func() {
			err := DeleteIPRange(ctx, &crimson.IPRangeDeleteList{})
			So(err, ShouldNotBeNil)
			// No queries
			_, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("with empty site returns an error", func() {
			err := DeleteIPRange(ctx, &crimson.IPRangeDeleteList{
				Ranges: []*crimson.IPRangeDelete{{VlanId: 1}}})
			So(err, ShouldNotBeNil)
			// No queries
			_, err = conn.PopOldestQuery()
			So(err, ShouldNotBeNil)
		})

		Convey("with invalid vlan ID returns an error", func() {
			err := DeleteIPRange(ctx, &crimson.IPRangeDeleteList{
				Ranges: []*crimson.IPRangeDelete{{Site: "site1", VlanId: 0}}})
			So(err, ShouldNotBeNil)
			// No queries
			_, err = conn.PopOldestQuery()
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
