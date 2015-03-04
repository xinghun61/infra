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
		err := BuildInstance(BuildInstanceOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Open it.
		inst, err := OpenInstance(bytes.NewReader(out.Bytes()), "")
		if inst != nil {
			defer inst.Close()
		}
		So(inst, ShouldNotBeNil)
		So(err, ShouldBeNil)
		So(inst.PackageName(), ShouldEqual, "testing")
		So(inst.InstanceID(), ShouldEqual, "23f2c4900785ac8faa2f38e473925b840e574ccc")
		So(len(inst.Files()), ShouldEqual, 1)

		// Contains single manifest file.
		f := inst.Files()[0]
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
		err := BuildInstance(BuildInstanceOptions{
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Attempt to open it, providing correct instance ID, should work.
		source := bytes.NewReader(out.Bytes())
		inst, err := OpenInstance(source, "23f2c4900785ac8faa2f38e473925b840e574ccc")
		So(err, ShouldBeNil)
		So(inst, ShouldNotBeNil)
		inst.Close()

		// Attempt to open it, providing incorrect instance ID.
		inst, err = OpenInstance(source, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
		So(err, ShouldNotBeNil)
		So(inst, ShouldBeNil)
	})

	Convey("OpenInstanceFile works", t, func() {
		// Open temp file.
		tempFile, err := ioutil.TempFile("", "cipdtest")
		So(err, ShouldBeNil)
		tempFilePath := tempFile.Name()
		defer os.Remove(tempFilePath)

		// Write empty package to it.
		err = BuildInstance(BuildInstanceOptions{
			Output:      tempFile,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)
		tempFile.Close()

		// Read the package.
		inst, err := OpenInstanceFile(tempFilePath, "")
		if inst != nil {
			defer inst.Close()
		}
		So(inst, ShouldNotBeNil)
		So(err, ShouldBeNil)
	})

	Convey("ExtractInstance works", t, func() {
		// Add a bunch of files to a package.
		out := bytes.Buffer{}
		err := BuildInstance(BuildInstanceOptions{
			Input: []File{
				makeTestFile("testing/qwerty", "12345", false),
				makeTestFile("abc", "duh", true),
				makeTestSymlink("rel_symlink", "abc"),
				makeTestSymlink("abs_symlink", "/abc/def"),
			},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// Extract files.
		inst, err := OpenInstance(bytes.NewReader(out.Bytes()), "")
		if inst != nil {
			defer inst.Close()
		}
		So(err, ShouldBeNil)
		dest := &testDestination{}
		err = ExtractInstance(inst, dest)
		So(err, ShouldBeNil)
		So(dest.beginCalls, ShouldEqual, 1)
		So(dest.endCalls, ShouldEqual, 1)

		// Verify file list, file data and flags are correct.
		names := []string{}
		for _, f := range dest.files {
			names = append(names, f.name)
		}
		So(names, ShouldResemble, []string{
			"testing/qwerty",
			"abc",
			"rel_symlink",
			"abs_symlink",
			".cipdpkg/manifest.json",
		})
		So(string(dest.files[0].Bytes()), ShouldEqual, "12345")
		So(dest.files[1].executable, ShouldBeTrue)
		So(dest.files[2].symlinkTarget, ShouldEqual, "abc")
		So(dest.files[3].symlinkTarget, ShouldEqual, "/abc/def")
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
	name          string
	executable    bool
	symlinkTarget string
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

func (d *testDestination) CreateSymlink(name string, target string) error {
	f := &testDestinationFile{
		name:          name,
		symlinkTarget: target,
	}
	d.files = append(d.files, f)
	return nil
}

func (d *testDestination) End(success bool) error {
	d.endCalls++
	return nil
}
