// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestReadManifest(t *testing.T) {
	var goodManifest = `{
  "format_version": "1",
  "package_name": "package/name"
}`

	Convey("readManifest can read valid manifest", t, func() {
		manifest, err := readManifest(strings.NewReader(goodManifest))
		So(manifest, ShouldResemble, Manifest{
			FormatVersion: "1",
			PackageName:   "package/name",
		})
		So(err, ShouldBeNil)
	})

	Convey("readManifest rejects invalid manifest", t, func() {
		manifest, err := readManifest(strings.NewReader("I'm not a manifest"))
		So(manifest, ShouldResemble, Manifest{})
		So(err, ShouldNotBeNil)
	})

	Convey("writeManifest works", t, func() {
		buf := &bytes.Buffer{}
		m := Manifest{
			FormatVersion: "1",
			PackageName:   "package/name",
		}
		So(writeManifest(&m, buf), ShouldBeNil)
		So(string(buf.Bytes()), ShouldEqual, goodManifest)
	})
}

func TestValidatePackageName(t *testing.T) {
	Convey("ValidatePackageName works", t, func() {
		So(ValidatePackageName("good/name"), ShouldBeNil)
		So(ValidatePackageName("good_name"), ShouldBeNil)
		So(ValidatePackageName("123-_/also/good/name"), ShouldBeNil)
		So(ValidatePackageName(""), ShouldNotBeNil)
		So(ValidatePackageName("BAD/name"), ShouldNotBeNil)
		So(ValidatePackageName("bad//name"), ShouldNotBeNil)
		So(ValidatePackageName("bad/name/"), ShouldNotBeNil)
		So(ValidatePackageName("bad.name"), ShouldNotBeNil)
		So(ValidatePackageName("/bad/name"), ShouldNotBeNil)
		So(ValidatePackageName("bad/name\nyeah"), ShouldNotBeNil)
		So(ValidatePackageName("../../yeah"), ShouldNotBeNil)
	})
}

func TestValidateInstanceID(t *testing.T) {
	Convey("ValidateInstanceID works", t, func() {
		So(ValidateInstanceID(""), ShouldNotBeNil)
		So(ValidateInstanceID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldBeNil)
		So(ValidateInstanceID("0123456789abcdefaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldBeNil)
		So(ValidateInstanceID("€aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldNotBeNil)
		So(ValidateInstanceID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldNotBeNil)
		So(ValidateInstanceID("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldNotBeNil)
		So(ValidateInstanceID("gaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldNotBeNil)
		So(ValidateInstanceID("AAAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), ShouldNotBeNil)
	})
}
