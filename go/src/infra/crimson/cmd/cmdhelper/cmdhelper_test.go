// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmdhelper

import (
	"encoding/json"
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	crimson "infra/crimson/proto"
)

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
			{"site1", "vlan1", "123.234.0.1", "123.234.1.244"},
			{"site2", "vlan2", "125.200.0.1", "126.233.1.255"},
		}

		Convey("for text format", func() {
			lines, err := FormatIPRange(ipRanges, textFormat)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site  vlan  Start IP    End IP        ",
				"site1 vlan1 123.234.0.1 123.234.1.244 ",
				"site2 vlan2 125.200.0.1 126.233.1.255 ",
			})
		})

		Convey("for CSV format", func() {
			lines, err := FormatIPRange(ipRanges, csvFormat)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site,vlan,Start IP,End IP",
				"site1,vlan1,123.234.0.1,123.234.1.244",
				"site2,vlan2,125.200.0.1,126.233.1.255",
			})
		})

		Convey("for CSV format with ',' in values", func() {
			ipRanges = append(ipRanges, &crimson.IPRange{
				Site:    "site,3",
				Vlan:    "vl,an3",
				StartIp: "1",
				EndIp:   "2",
			})
			lines, err := FormatIPRange(ipRanges, csvFormat)
			So(err, ShouldBeNil)
			So(lines, ShouldResemble, []string{
				"site,vlan,Start IP,End IP",
				"site1,vlan1,123.234.0.1,123.234.1.244",
				"site2,vlan2,125.200.0.1,126.233.1.255",
				"\"site,3\",\"vl,an3\",1,2",
			})
		})

		Convey("for JSON format", func() {
			lines, err := FormatIPRange(ipRanges, jsonFormat)
			So(err, ShouldBeNil)
			So(len(lines), ShouldEqual, 1)
			var outIPRanges []*crimson.IPRange
			json.Unmarshal([]byte(lines[0]), &outIPRanges)
			So(outIPRanges, ShouldResemble, ipRanges)
		})
	})
}
