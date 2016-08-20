// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package netutil

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"
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
