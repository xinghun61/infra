// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"io"
	"io/ioutil"
	"os"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPackageReading(t *testing.T) {
	goodManifest := `{
  "format_version": "1",
  "package_name": "testing"
}`

	Convey("Open empty package works", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Open it.
		pkg, err := OpenPackage(bytes.NewReader(out.Bytes()), "")
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(pkg.Name(), ShouldEqual, "testing")
		So(pkg.InstanceID(), ShouldEqual, "23f2c4900785ac8faa2f38e473925b840e574ccc")
		So(len(pkg.Files()), ShouldEqual, 1)

		// Contains single manifest file.
		f := pkg.Files()[0]
		So(f.Name(), ShouldEqual, ".cipdpkg/manifest.json")
		So(f.Size(), ShouldEqual, uint64(len(goodManifest)))
		So(f.Executable(), ShouldBeFalse)
		r, err := f.Open()
		if r != nil {
			defer r.Close()
		}
		So(err, ShouldBeNil)
		manifest, err := ioutil.ReadAll(r)
		So(err, ShouldBeNil)
		So(string(manifest), ShouldEqual, goodManifest)
	})

	Convey("Open empty package with unexpected instance ID", t, func() {
		// Build an empty package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Attempt to open it, providing correct instance ID, should work.
		source := bytes.NewReader(out.Bytes())
		pkg, err := OpenPackage(source, "23f2c4900785ac8faa2f38e473925b840e574ccc")
		So(err, ShouldBeNil)
		So(pkg, ShouldNotBeNil)
		pkg.Close()

		// Attempt to open it, providing incorrect instance ID.
		pkg, err = OpenPackage(source, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
		So(err, ShouldNotBeNil)
		So(pkg, ShouldBeNil)
	})

	Convey("OpenPackageFile works", t, func() {
		// Open temp file.
		tempFile, err := ioutil.TempFile("", "cipdtest")
		So(err, ShouldBeNil)
		tempFilePath := tempFile.Name()
		defer os.Remove(tempFilePath)

		// Write empty package to it.
		err = BuildPackage(BuildPackageOptions{
			Output:      tempFile,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)
		tempFile.Close()

		// Read the package.
		pkg, err := OpenPackageFile(tempFilePath, "")
		if pkg != nil {
			defer pkg.Close()
		}
		So(pkg, ShouldNotBeNil)
		So(err, ShouldBeNil)
	})

	Convey("ExtractPackage works", t, func() {
		// Add a bunch of files to a package.
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Input: []File{
				makeTestFile("testing/qwerty", "12345", false),
				makeTestFile("abc", "duh", true),
			},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Extract files.
		pkg, err := OpenPackage(bytes.NewReader(out.Bytes()), "")
		if pkg != nil {
			defer pkg.Close()
		}
		So(err, ShouldBeNil)
		dest := &testDestination{}
		err = ExtractPackage(pkg, dest)
		So(err, ShouldBeNil)
		So(dest.beginCalls, ShouldEqual, 1)
		So(dest.endCalls, ShouldEqual, 1)
		So(len(dest.files), ShouldEqual, 3)

		// Verify file list, file data and flags are correct.
		names := []string{}
		for _, f := range dest.files {
			names = append(names, f.name)
		}
		So(names, ShouldResemble, []string{
			"testing/qwerty",
			"abc",
			".cipdpkg/manifest.json",
		})
		So(string(dest.files[0].Bytes()), ShouldEqual, "12345")
		So(dest.files[1].executable, ShouldBeTrue)
	})
}

////////////////////////////////////////////////////////////////////////////////

type testDestination struct {
	beginCalls int
	endCalls   int
	files      []*testDestinationFile
}

type testDestinationFile struct {
	bytes.Buffer
	name       string
	executable bool
}

func (d *testDestinationFile) Close() error { return nil }

func (d *testDestination) Begin() error {
	d.beginCalls++
	return nil
}

func (d *testDestination) CreateFile(name string, executable bool) (io.WriteCloser, error) {
	f := &testDestinationFile{
		name:       name,
		executable: executable,
	}
	d.files = append(d.files, f)
	return f, nil
}

func (d *testDestination) End(success bool) error {
	d.endCalls++
	return nil
}
