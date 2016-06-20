// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package crimsondb

import (
	"database/sql/driver"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"

	"infra/crimson/proto"
	"infra/crimson/server/sqlmock"
)

func TestIPStringToHexString(t *testing.T) {
	hexString := IPStringToHexString("192.168.0.1")
	expected := "0xc0a80001"
	if hexString != expected {
		t.Error("Hex string is different from expected value:",
			hexString, "vs", expected)
	}

	hexString = IPStringToHexString("0.0.0.0")
	expected = "0x00000000"
	if hexString != expected {
		t.Error("Hex string is different from expected value:",
			hexString, "vs", expected)
	}
}

func TestHexStringToIPString(t *testing.T) {
	ipString := HexStringToIP("0x00000000").String()
	expected := "0.0.0.0"
	if ipString != expected {
		t.Error("IP string is different from expected value:",
			ipString, "vs", expected)
	}

	ipString = HexStringToIP("0xc0a80001").String()
	expected = "192.168.0.1"
	if ipString != expected {
		t.Error("IP string is different from expected value:",
			ipString, "vs", expected)
	}
}

func TestIPStringToHexAndBack(t *testing.T) {
	// Check that function which are supposed to be exact inverse actually are.
	ip1 := "135.45.1.84"
	ip2 := HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}

	ip1 = "1.2.3.4"
	ip2 = HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}

	ip1 = "255.255.255.255"
	ip2 = HexStringToIP(IPStringToHexString(ip1)).String()
	if ip1 != ip2 {
		t.Error("IP string is different from expected value:",
			ip1, "vs", ip2)
	}
}

func TestSelectIPRange(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	db, conn := sqlmock.NewMockDB()
	ctx = context.WithValue(ctx, "dbHandle", db)

	Convey("SelectIPRange", t, func() {
		Convey("without parameter", func() {
			SelectIPRange(ctx, &crimson.IPRangeQuery{})
			query, err := conn.PopOldestQuery()
			Convey("generates a SQL query", func() {
				So(err, ShouldBeNil)
			})
			Convey("generates the correct query", func() {
				expected := "SELECT vlan, site, start_ip, end_ip FROM ip_range"
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
				expected := ("SELECT vlan, site, start_ip, end_ip FROM ip_range\n" +
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
				expected := ("SELECT vlan, site, start_ip, end_ip FROM ip_range\n" +
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
				expected := ("SELECT vlan, site, start_ip, end_ip FROM ip_range\n" +
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
				expected := ("SELECT vlan, site, start_ip, end_ip FROM ip_range\n" +
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
				expected := ("SELECT vlan, site, start_ip, end_ip FROM ip_range\n" +
					"LIMIT ?")
				So(query.Query, ShouldEqual, expected)
				So(query.Args, ShouldResemble, []driver.Value{int64(14)})
			})
		})
	})
}
