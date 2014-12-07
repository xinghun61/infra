// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUtilities(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		// Wrappers that accept paths relative to tempDir.
		touch := func(rel string) {
			abs := filepath.Join(tempDir, filepath.FromSlash(rel))
			err := os.MkdirAll(filepath.Dir(abs), 0777)
			So(err, ShouldBeNil)
			f, err := os.Create(abs)
			So(err, ShouldBeNil)
			f.Close()
		}
		ensureLink := func(symlinkRel string, target string) error {
			return ensureSymlink(filepath.Join(tempDir, symlinkRel), target)
		}
		readLink := func(symlinkRel string) string {
			val, err := os.Readlink(filepath.Join(tempDir, symlinkRel))
			So(err, ShouldBeNil)
			return val
		}

		Convey("ensureSymlink creates new symlink", func() {
			So(ensureLink("symlink", "target"), ShouldBeNil)
			So(readLink("symlink"), ShouldEqual, "target")
		})

		Convey("ensureSymlink builds full path", func() {
			So(ensureLink(filepath.Join("a", "b", "c"), "target"), ShouldBeNil)
			So(readLink(filepath.Join("a", "b", "c")), ShouldEqual, "target")
		})

		Convey("ensureSymlink replaces existing one", func() {
			So(ensureLink("symlink", "target"), ShouldBeNil)
			So(ensureLink("symlink", "another"), ShouldBeNil)
			So(readLink("symlink"), ShouldEqual, "another")
		})

		Convey("scanPackageDir works with empty dir", func() {
			err := os.Mkdir(filepath.Join(tempDir, "dir"), 0777)
			So(err, ShouldBeNil)
			files := makeStringSet()
			err = scanPackageDir(filepath.Join(tempDir, "dir"), files)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 0)
		})

		Convey("scanPackageDir works", func() {
			touch("unrelated/1")
			touch("dir/a/1")
			touch("dir/a/2")
			touch("dir/b/1")
			touch("dir/.cipdpkg/abc")
			touch("dir/.cipd/abc")
			ensureLink("dir/a/link", "target")
			files := makeStringSet()
			err := scanPackageDir(filepath.Join(tempDir, "dir"), files)
			So(err, ShouldBeNil)
			names := sort.StringSlice{}
			for n := range files {
				names = append(names, filepath.ToSlash(n))
			}
			names.Sort()
			So(names, ShouldResemble, sort.StringSlice{
				"a/1",
				"a/2",
				"b/1",
			})
		})

		Convey("ensureDirectoryGone works with missing dir", func() {
			So(ensureDirectoryGone(filepath.Join(tempDir, "missing")), ShouldBeNil)
		})

		Convey("ensureDirectoryGone works", func() {
			touch("dir/a/1")
			touch("dir/a/2")
			touch("dir/b/1")
			So(ensureDirectoryGone(filepath.Join(tempDir, "dir")), ShouldBeNil)
			_, err := os.Stat(filepath.Join(tempDir, "dir"))
			So(os.IsNotExist(err), ShouldBeTrue)
		})
	})
}

func TestDeploy(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		Convey("Deploy new empty package", func() {
			pkg := makeTestPackage("test/package", []File{})
			info, err := Deploy(tempDir, pkg)
			So(err, ShouldBeNil)
			So(info, ShouldResemble, DeployedPackageInfo{
				InstanceID: pkg.InstanceID(),
				Manifest: Manifest{
					FormatVersion: "1",
					PackageName:   "test/package",
				},
			})
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/_current:0123456789abcdef00000123456789abcdef0000",
			})
		})

		Convey("Deploy new non-empty package", func() {
			pkg := makeTestPackage("test/package", []File{
				makeTestFile("some/file/path", "data a", false),
				makeTestFile("some/executable", "data b", true),
			})
			_, err := Deploy(tempDir, pkg)
			So(err, ShouldBeNil)
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/some/executable*",
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/some/file/path",
				".cipd/pkgs/test/package/_current:0123456789abcdef00000123456789abcdef0000",
				"some/executable:../.cipd/pkgs/test/package/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test/package/_current/some/file/path",
			})
			// Ensure symlinks are actually traversable.
			body, err := ioutil.ReadFile(filepath.Join(tempDir, "some", "file", "path"))
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, "data a")
		})

		Convey("Redeploy same package instance", func() {
			pkg := makeTestPackage("test/package", []File{
				makeTestFile("some/file/path", "data a", false),
				makeTestFile("some/executable", "data b", true),
			})
			_, err := Deploy(tempDir, pkg)
			So(err, ShouldBeNil)
			_, err = Deploy(tempDir, pkg)
			So(err, ShouldBeNil)
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/some/executable*",
				".cipd/pkgs/test/package/0123456789abcdef00000123456789abcdef0000/some/file/path",
				".cipd/pkgs/test/package/_current:0123456789abcdef00000123456789abcdef0000",
				"some/executable:../.cipd/pkgs/test/package/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test/package/_current/some/file/path",
			})
		})

		Convey("Deploy package update", func() {
			oldPkg := makeTestPackage("test/package", []File{
				makeTestFile("some/file/path", "data a old", false),
				makeTestFile("some/executable", "data b old", true),
				makeTestFile("old only", "data c old", true),
				makeTestFile("mode change 1", "data d", true),
				makeTestFile("mode change 2", "data e", false),
			})
			oldPkg.instanceID = "0000000000000000000000000000000000000000"

			newPkg := makeTestPackage("test/package", []File{
				makeTestFile("some/file/path", "data a new", false),
				makeTestFile("some/executable", "data b new", true),
				makeTestFile("mode change 1", "data d", false),
				makeTestFile("mode change 2", "data d", true),
			})
			newPkg.instanceID = "1111111111111111111111111111111111111111"

			_, err := Deploy(tempDir, oldPkg)
			So(err, ShouldBeNil)
			_, err = Deploy(tempDir, newPkg)
			So(err, ShouldBeNil)

			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test/package/1111111111111111111111111111111111111111/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/1111111111111111111111111111111111111111/mode change 1",
				".cipd/pkgs/test/package/1111111111111111111111111111111111111111/mode change 2*",
				".cipd/pkgs/test/package/1111111111111111111111111111111111111111/some/executable*",
				".cipd/pkgs/test/package/1111111111111111111111111111111111111111/some/file/path",
				".cipd/pkgs/test/package/_current:1111111111111111111111111111111111111111",
				"mode change 1:.cipd/pkgs/test/package/_current/mode change 1",
				"mode change 2:.cipd/pkgs/test/package/_current/mode change 2",
				"some/executable:../.cipd/pkgs/test/package/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test/package/_current/some/file/path",
			})
		})

		Convey("Deploy two different package", func() {
			pkg1 := makeTestPackage("test/package", []File{
				makeTestFile("some/file/path", "data a old", false),
				makeTestFile("some/executable", "data b old", true),
				makeTestFile("pkg1 file", "data c", false),
			})
			pkg1.instanceID = "0000000000000000000000000000000000000000"

			// Nesting in package names is allowed.
			pkg2 := makeTestPackage("test/package/another", []File{
				makeTestFile("some/file/path", "data a new", false),
				makeTestFile("some/executable", "data b new", true),
				makeTestFile("pkg2 file", "data d", false),
			})
			pkg2.instanceID = "1111111111111111111111111111111111111111"

			_, err := Deploy(tempDir, pkg1)
			So(err, ShouldBeNil)
			_, err = Deploy(tempDir, pkg2)
			So(err, ShouldBeNil)

			// TODO: Conflicting symlinks point to last installed package, it is not
			// very deterministic.
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test/package/0000000000000000000000000000000000000000/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/0000000000000000000000000000000000000000/pkg1 file",
				".cipd/pkgs/test/package/0000000000000000000000000000000000000000/some/executable*",
				".cipd/pkgs/test/package/0000000000000000000000000000000000000000/some/file/path",
				".cipd/pkgs/test/package/_current:0000000000000000000000000000000000000000",
				".cipd/pkgs/test/package/another/1111111111111111111111111111111111111111/.cipdpkg/manifest.json",
				".cipd/pkgs/test/package/another/1111111111111111111111111111111111111111/pkg2 file",
				".cipd/pkgs/test/package/another/1111111111111111111111111111111111111111/some/executable*",
				".cipd/pkgs/test/package/another/1111111111111111111111111111111111111111/some/file/path",
				".cipd/pkgs/test/package/another/_current:1111111111111111111111111111111111111111",
				"pkg1 file:.cipd/pkgs/test/package/_current/pkg1 file",
				"pkg2 file:.cipd/pkgs/test/package/another/_current/pkg2 file",
				"some/executable:../.cipd/pkgs/test/package/another/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test/package/another/_current/some/file/path",
			})
		})

		Convey("Try to deploy package with bad name", func() {
			_, err := Deploy(tempDir, makeTestPackage("../test/package", []File{}))
			So(err, ShouldNotBeNil)
		})

		Convey("Try to deploy package with bad instance ID", func() {
			pkg := makeTestPackage("test/package", []File{})
			pkg.instanceID = "../000000000"
			_, err := Deploy(tempDir, pkg)
			So(err, ShouldNotBeNil)
		})

		Convey("Try to deploy unsigned package", func() {
			pkg := makeTestPackage("test/package", []File{})
			pkg.signed = false
			_, err := Deploy(tempDir, pkg)
			So(err, ShouldNotBeNil)
		})
	})
}

////////////////////////////////////////////////////////////////////////////////

type testPackage struct {
	name       string
	instanceID string
	files      []File
	signed     bool
}

// makeTestPackage returns Package implementation with mocked guts.
func makeTestPackage(name string, files []File) *testPackage {
	// Generate and append manifest file.
	out := bytes.Buffer{}
	err := writeManifest(&Manifest{
		FormatVersion: manifestFormatVersion,
		PackageName:   name,
	}, &out)
	if err != nil {
		panic("Failed to write a manifest")
	}
	files = append(files, makeTestFile(manifestName, string(out.Bytes()), false))
	return &testPackage{
		name:       name,
		instanceID: "0123456789abcdef00000123456789abcdef0000",
		files:      files,
		signed:     true,
	}
}

func (f *testPackage) Close() error       { return nil }
func (f *testPackage) Signed() bool       { return f.signed }
func (f *testPackage) Name() string       { return f.name }
func (f *testPackage) InstanceID() string { return f.instanceID }
func (f *testPackage) Files() []File      { return f.files }

func (f *testPackage) Signatures() []SignatureBlock {
	panic("Not implemented")
	return []SignatureBlock{}
}

func (f *testPackage) DataReader() (io.Reader, error) {
	panic("Not implemented")
	return nil, nil
}

////////////////////////////////////////////////////////////////////////////////

// scanDir returns list of files (regular and symlinks) it finds in a directory.
// Symlinks are returned as "path:target". Regular executable files are suffixed
// with '*'. All paths are relative to the scanned directory and slash
// separated. Symlink targets are slash separated too, but otherwise not
// modified. Does not look inside symlinked directories.
func scanDir(root string) (out []string) {
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		if info.Mode().IsDir() {
			return nil
		}

		rel = filepath.ToSlash(rel)
		target, err := os.Readlink(path)
		var item string
		if err == nil {
			item = fmt.Sprintf("%s:%s", rel, filepath.ToSlash(target))
		} else {
			if info.Mode().IsRegular() {
				item = rel
			} else {
				item = fmt.Sprintf("%s:??????", rel)
			}
		}

		suffix := ""
		if info.Mode().IsRegular() && (info.Mode().Perm()&0100) != 0 {
			suffix = "*"
		}

		out = append(out, item+suffix)
		return nil
	})
	if err != nil {
		panic("Failed to walk a directory")
	}
	return
}
