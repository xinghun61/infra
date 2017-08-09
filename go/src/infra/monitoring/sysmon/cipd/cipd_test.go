// Copyright (c) 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	local "go.chromium.org/luci/cipd/client/cipd/local"

	. "github.com/smartystreets/goconvey/convey"
)

func TestListFiles(t *testing.T) {
	Convey("In a temporary directory", t, func() {
		path, err := ioutil.TempDir("", "cipd-test")
		So(err, ShouldBeNil)
		defer os.RemoveAll(path)

		Convey("finds a file called CIPD_VERSION.json", func() {
			err := ioutil.WriteFile(filepath.Join(path, "CIPD_VERSION.json"), []byte{}, 0644)
			So(err, ShouldBeNil)

			So(listCIPDVersionFiles(path), ShouldResemble, []string{
				filepath.Join(path, "CIPD_VERSION.json"),
			})
		})

		Convey("finds a file called foo.cipd_version", func() {
			err := ioutil.WriteFile(filepath.Join(path, "foo.cipd_version"), []byte{}, 0644)
			So(err, ShouldBeNil)

			So(listCIPDVersionFiles(path), ShouldResemble, []string{
				filepath.Join(path, "foo.cipd_version"),
			})
		})

		Convey("reads a file", func() {
			err := ioutil.WriteFile(filepath.Join(path, "foo.cipd_version"), []byte(`
        {
          "package_name": "Hello",
          "instance_id": "World"
        }
      `), 0644)
			So(err, ShouldBeNil)

			f, err := readCIPDVersionFile(filepath.Join(path, "foo.cipd_version"))
			So(err, ShouldBeNil)
			So(f, ShouldResemble, local.VersionFile{
				PackageName: "Hello",
				InstanceID:  "World",
			})
		})

		Convey("file doesn't exist", func() {
			f, err := readCIPDVersionFile(filepath.Join(path, "does not exist"))
			So(err, ShouldBeNil)
			So(f, ShouldResemble, local.VersionFile{})
		})
	})
}
