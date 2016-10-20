// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"os"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
)

func TestReadDhcpdConfFile(t *testing.T) {
	t.Parallel()
	Convey("Reading dhcpd.*.conf file works", t, func() {
		Convey("for a valid file", func() {
			fileName := filepath.Join("testdata", "dhcpd.good.conf")
			file, err := os.Open(fileName)
			So(err, ShouldBeNil)
			defer file.Close()

			site := "test-site"
			expected := []*crimson.IPRange{
				{
					Site:      site,
					VlanId:    42,
					StartIp:   "192.168.42.1",
					EndIp:     "192.168.42.244",
					VlanAlias: "vlan_42",
				},
				{
					Site:      site,
					VlanId:    42,
					StartIp:   "192.168.42.250",
					EndIp:     "192.168.43.254",
					VlanAlias: "vlan_42",
				},
				{
					Site:      "test-site",
					VlanId:    1,
					StartIp:   "127.0.0.0",
					EndIp:     "127.0.3.255",
					VlanAlias: "localhost-no-ranges",
				},
			}

			ranges, err := ReadDhcpdConfFile(file, site)
			So(err, ShouldBeNil)
			So(ranges, ShouldResemble, expected)
		})

	})
}

func TestGetVlanFromCommentVlanName(t *testing.T) {
	t.Parallel()
	Convey("Getting vlan-name from a comment works", t, func() {
		Convey("with normal formatting", func() {
			line := "# @vlan-name: blah"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with no space after #", func() {
			line := "#@vlan-name: blah"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with no space after ':'", func() {
			line := "# @vlan-name:blah"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with space before ':'", func() {
			line := "# @vlan-name :blah"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with multiple spaces before name", func() {
			line := "# @vlan-name:    blah"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with trailing space", func() {
			line := "# @vlan-name: blah    "
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, "blah")
		})

		Convey("with weird characters in the name", func() {
			weirdName := "abAZ09/@._-"
			line := "# @vlan-name: " + weirdName
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanName, ShouldEqual, weirdName)
		})

		Convey("spaces in vlan names are not allowed", func() {
			line := "# @vlan-name: blah_1 triggers an error"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldNotBeNil)
			So(names.vlanName, ShouldEqual, "")
		})
	})
}

func TestMismatchingComments(t *testing.T) {
	t.Parallel()
	Convey("Mismatching comments are ignored", t, func() {
		names := vlanNames{
			vlanName:   "name sentinel",
			vlanSuffix: "suffix sentinel",
		}
		origNames := names
		Convey("Garbage in comment is ignored", func() {
			line := "asdjfk; epy53 fq8071ht4"
			err := names.getVlanFromComment(line)
			So(err, ShouldNotBeNil)
			So(names, ShouldResemble, origNames)
		})
		Convey("Missing vlan name ", func() {
			line := "# @vlan-name:  "
			err := names.getVlanFromComment(line)
			So(err, ShouldNotBeNil)
			So(names, ShouldResemble, origNames)
		})
	})
}

func TestVlanSuffixFromComments(t *testing.T) {
	t.Parallel()
	Convey("Getting vlan-suffix from comment works", t, func() {
		Convey("with normal formatting", func() {
			line := "# @vlan-suffix: -m1"
			names := vlanNames{}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanSuffix, ShouldEqual, "-m1")
		})

		Convey("with normal formatting + existing vlanName", func() {
			line := "# @vlan-suffix: -m1"
			names := vlanNames{vlanName: "name sentinel"}
			err := names.getVlanFromComment(line)
			So(err, ShouldBeNil)
			So(names.vlanSuffix, ShouldEqual, "-m1")
			So(names.vlanName, ShouldEqual, "name sentinel")
		})
	})
}
