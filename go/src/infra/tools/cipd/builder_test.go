// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"archive/zip"
	"bytes"
	"crypto/sha1"
	"encoding/hex"
	"io"
	"io/ioutil"
	"os"
	"runtime"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGoVersion(t *testing.T) {
	Convey("Make sure using pinned Go version", t, func() {
		// Change this when rolling pinned Go version. Some tests here may depend
		// on zlib implementation details compiled in Go stdlib.
		So(runtime.Version(), ShouldEqual, "go1.4")
	})
}

func TestBuildPackage(t *testing.T) {
	const goodManifest = `{
  "format_version": "1",
  "package_name": "testing"
}`

	Convey("Building empty package", t, func() {
		out := bytes.Buffer{}
		err := BuildPackage(BuildPackageOptions{
			Input:       []File{},
			Output:      &out,
			PackageName: "testing",
		})
		So(err, ShouldBeNil)

		// BuildPackage builds deterministic zip. It MUST NOT depend on
		// the platform, or a time of day, or anything else, only on the input data.
		So(getSHA1(&out), ShouldEqual, "23f2c4900785ac8faa2f38e473925b840e574ccc")

		// There should be a single file: the manifest.
		files := readZip(out.Bytes())
		So(files, ShouldResemble, []zippedFile{
			zippedFile{
				// See structs.go, manifestName.
				name: ".cipdpkg/manifest.json",
				size: uint64(len(goodManifest)),
				mode: 0600,
				body: []byte(goodManifest),
			},
		})
	})

	Convey("Building package with a bunch of files", t, func() {
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

		// The manifest and all added files.
		files := readZip(out.Bytes())
		So(files, ShouldResemble, []zippedFile{
			zippedFile{
				name: "testing/qwerty",
				size: 5,
				mode: 0600,
				body: []byte("12345"),
			},
			zippedFile{
				name: "abc",
				size: 3,
				mode: 0700,
				body: []byte("duh"),
			},
			zippedFile{
				// See structs.go, manifestName.
				name: ".cipdpkg/manifest.json",
				size: uint64(len(goodManifest)),
				mode: 0600,
				body: []byte(goodManifest),
			},
		})
	})

	Convey("Duplicate files fail", t, func() {
		err := BuildPackage(BuildPackageOptions{
			Input: []File{
				makeTestFile("a", "12345", false),
				makeTestFile("a", "12345", false),
			},
			Output:      &bytes.Buffer{},
			PackageName: "testing",
		})
		So(err, ShouldNotBeNil)
	})

	Convey("Writing to service dir fails", t, func() {
		err := BuildPackage(BuildPackageOptions{
			Input: []File{
				makeTestFile(".cipdpkg/stuff", "12345", false),
			},
			Output:      &bytes.Buffer{},
			PackageName: "testing",
		})
		So(err, ShouldNotBeNil)
	})

	Convey("Bad name fails", t, func() {
		err := BuildPackage(BuildPackageOptions{
			Output:      &bytes.Buffer{},
			PackageName: "../../asdad",
		})
		So(err, ShouldNotBeNil)
	})

}

////////////////////////////////////////////////////////////////////////////////

// getSHA1 returns SHA1 hex digest of a byte buffer.
func getSHA1(buf *bytes.Buffer) string {
	h := sha1.New()
	h.Write(buf.Bytes())
	return hex.EncodeToString(h.Sum(nil))
}

////////////////////////////////////////////////////////////////////////////////

type zippedFile struct {
	name string
	size uint64
	mode os.FileMode
	body []byte
}

// readZip scans zip directory and returns files it finds.
func readZip(data []byte) []zippedFile {
	z, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		panic("Failed to open zip file")
	}
	files := make([]zippedFile, len(z.File))
	for i, zf := range z.File {
		reader, err := zf.Open()
		if err != nil {
			panic("Failed to open file inside zip")
		}
		body, err := ioutil.ReadAll(reader)
		if err != nil {
			panic("Failed to read zipped file")
		}
		files[i] = zippedFile{
			name: zf.Name,
			size: zf.FileHeader.UncompressedSize64,
			mode: zf.Mode(),
			body: body,
		}
	}
	return files
}

////////////////////////////////////////////////////////////////////////////////

type testFile struct {
	name       string
	data       string
	executable bool
}

func (f *testFile) Name() string     { return f.name }
func (f *testFile) Size() uint64     { return uint64(len(f.data)) }
func (f *testFile) Executable() bool { return f.executable }
func (f *testFile) Open() (io.ReadCloser, error) {
	r := bytes.NewReader([]byte(f.data))
	return ioutil.NopCloser(r), nil
}

func makeTestFile(name string, data string, executable bool) File {
	return &testFile{
		name:       name,
		data:       data,
		executable: executable,
	}
}
