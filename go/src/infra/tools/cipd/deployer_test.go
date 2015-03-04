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
			ensureLink("dir/a/sym_link", "target")
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
				"a/sym_link",
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

		Convey("ensureFileGone works", func() {
			touch("abc")
			So(ensureFileGone(filepath.Join(tempDir, "abc")), ShouldBeNil)
			_, err := os.Stat(filepath.Join(tempDir, "abc"))
			So(os.IsNotExist(err), ShouldBeTrue)
		})

		Convey("ensureFileGone works with missing file", func() {
			So(ensureFileGone(filepath.Join(tempDir, "abc")), ShouldBeNil)
		})

		Convey("ensureFileGone works with symlink", func() {
			ensureLink("abc", "target")
			So(ensureFileGone(filepath.Join(tempDir, "abc")), ShouldBeNil)
			_, err := os.Stat(filepath.Join(tempDir, "abc"))
			So(os.IsNotExist(err), ShouldBeTrue)
		})
	})
}

func TestDeployInstance(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		Convey("DeployInstance new empty package instance", func() {
			inst := makeTestInstance("test/package", nil)
			info, err := DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)
			So(info, ShouldResemble, PackageState{
				PackageName: "test/package",
				InstanceID:  inst.InstanceID(),
			})
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test_package_B6R4ErK5ko/_current:0123456789abcdef00000123456789abcdef0000",
			})
		})

		Convey("DeployInstance new non-empty package instance", func() {
			inst := makeTestInstance("test/package", []File{
				makeTestFile("some/file/path", "data a", false),
				makeTestFile("some/executable", "data b", true),
				makeTestSymlink("some/symlink", "executable"),
			})
			_, err := DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/executable*",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/file/path",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/symlink:executable",
				".cipd/pkgs/test_package_B6R4ErK5ko/_current:0123456789abcdef00000123456789abcdef0000",
				"some/executable:../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/file/path",
				"some/symlink:../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/symlink",
			})
			// Ensure symlinks are actually traversable.
			body, err := ioutil.ReadFile(filepath.Join(tempDir, "some", "file", "path"))
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, "data a")
			// Symlink to symlink is traversable too.
			body, err = ioutil.ReadFile(filepath.Join(tempDir, "some", "symlink"))
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, "data b")
		})

		Convey("Redeploy same package instance", func() {
			inst := makeTestInstance("test/package", []File{
				makeTestFile("some/file/path", "data a", false),
				makeTestFile("some/executable", "data b", true),
				makeTestSymlink("some/symlink", "executable"),
			})
			_, err := DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/executable*",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/file/path",
				".cipd/pkgs/test_package_B6R4ErK5ko/0123456789abcdef00000123456789abcdef0000/some/symlink:executable",
				".cipd/pkgs/test_package_B6R4ErK5ko/_current:0123456789abcdef00000123456789abcdef0000",
				"some/executable:../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/file/path",
				"some/symlink:../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/symlink",
			})
		})

		Convey("DeployInstance package update", func() {
			oldPkg := makeTestInstance("test/package", []File{
				makeTestFile("some/file/path", "data a old", false),
				makeTestFile("some/executable", "data b old", true),
				makeTestFile("old only", "data c old", true),
				makeTestFile("mode change 1", "data d", true),
				makeTestFile("mode change 2", "data e", false),
				makeTestSymlink("symlink unchanged", "target"),
				makeTestSymlink("symlink changed", "old target"),
				makeTestSymlink("symlink removed", "target"),
			})
			oldPkg.instanceID = "0000000000000000000000000000000000000000"

			newPkg := makeTestInstance("test/package", []File{
				makeTestFile("some/file/path", "data a new", false),
				makeTestFile("some/executable", "data b new", true),
				makeTestFile("mode change 1", "data d", false),
				makeTestFile("mode change 2", "data d", true),
				makeTestSymlink("symlink unchanged", "target"),
				makeTestSymlink("symlink changed", "new target"),
			})
			newPkg.instanceID = "1111111111111111111111111111111111111111"

			_, err := DeployInstance(tempDir, oldPkg)
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, newPkg)
			So(err, ShouldBeNil)

			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/.cipdpkg/manifest.json",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/mode change 1",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/mode change 2*",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/some/executable*",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/some/file/path",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/symlink changed:new target",
				".cipd/pkgs/test_package_B6R4ErK5ko/1111111111111111111111111111111111111111/symlink unchanged:target",
				".cipd/pkgs/test_package_B6R4ErK5ko/_current:1111111111111111111111111111111111111111",
				"mode change 1:.cipd/pkgs/test_package_B6R4ErK5ko/_current/mode change 1",
				"mode change 2:.cipd/pkgs/test_package_B6R4ErK5ko/_current/mode change 2",
				"some/executable:../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/test_package_B6R4ErK5ko/_current/some/file/path",
				"symlink changed:.cipd/pkgs/test_package_B6R4ErK5ko/_current/symlink changed",
				"symlink unchanged:.cipd/pkgs/test_package_B6R4ErK5ko/_current/symlink unchanged",
			})
		})

		Convey("DeployInstance two different packages", func() {
			pkg1 := makeTestInstance("test/package", []File{
				makeTestFile("some/file/path", "data a old", false),
				makeTestFile("some/executable", "data b old", true),
				makeTestFile("pkg1 file", "data c", false),
			})
			pkg1.instanceID = "0000000000000000000000000000000000000000"

			// Nesting in package names is allowed.
			pkg2 := makeTestInstance("test/package/another", []File{
				makeTestFile("some/file/path", "data a new", false),
				makeTestFile("some/executable", "data b new", true),
				makeTestFile("pkg2 file", "data d", false),
			})
			pkg2.instanceID = "1111111111111111111111111111111111111111"

			_, err := DeployInstance(tempDir, pkg1)
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, pkg2)
			So(err, ShouldBeNil)

			// TODO: Conflicting symlinks point to last installed package, it is not
			// very deterministic.
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/package_another_4HL4H61fGm/1111111111111111111111111111111111111111/.cipdpkg/manifest.json",
				".cipd/pkgs/package_another_4HL4H61fGm/1111111111111111111111111111111111111111/pkg2 file",
				".cipd/pkgs/package_another_4HL4H61fGm/1111111111111111111111111111111111111111/some/executable*",
				".cipd/pkgs/package_another_4HL4H61fGm/1111111111111111111111111111111111111111/some/file/path",
				".cipd/pkgs/package_another_4HL4H61fGm/_current:1111111111111111111111111111111111111111",
				".cipd/pkgs/test_package_B6R4ErK5ko/0000000000000000000000000000000000000000/.cipdpkg/manifest.json",
				".cipd/pkgs/test_package_B6R4ErK5ko/0000000000000000000000000000000000000000/pkg1 file",
				".cipd/pkgs/test_package_B6R4ErK5ko/0000000000000000000000000000000000000000/some/executable*",
				".cipd/pkgs/test_package_B6R4ErK5ko/0000000000000000000000000000000000000000/some/file/path",
				".cipd/pkgs/test_package_B6R4ErK5ko/_current:0000000000000000000000000000000000000000",
				"pkg1 file:.cipd/pkgs/test_package_B6R4ErK5ko/_current/pkg1 file",
				"pkg2 file:.cipd/pkgs/package_another_4HL4H61fGm/_current/pkg2 file",
				"some/executable:../.cipd/pkgs/package_another_4HL4H61fGm/_current/some/executable",
				"some/file/path:../../.cipd/pkgs/package_another_4HL4H61fGm/_current/some/file/path",
			})
		})

		Convey("Try to deploy package instance with bad package name", func() {
			_, err := DeployInstance(tempDir, makeTestInstance("../test/package", nil))
			So(err, ShouldNotBeNil)
		})

		Convey("Try to deploy package instance with bad instance ID", func() {
			inst := makeTestInstance("test/package", nil)
			inst.instanceID = "../000000000"
			_, err := DeployInstance(tempDir, inst)
			So(err, ShouldNotBeNil)
		})
	})
}

func TestFindDeployed(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		Convey("FindDeployed works with empty dir", func() {
			out, err := FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(out, ShouldBeNil)
		})

		Convey("FindDeployed works", func() {
			// Deploy a bunch of stuff.
			_, err := DeployInstance(tempDir, makeTestInstance("test/pkg/123", nil))
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, makeTestInstance("test/pkg/456", nil))
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, makeTestInstance("test/pkg", nil))
			So(err, ShouldBeNil)
			_, err = DeployInstance(tempDir, makeTestInstance("test", nil))
			So(err, ShouldBeNil)

			// Verify it is discoverable.
			out, err := FindDeployed(tempDir)
			So(err, ShouldBeNil)
			So(out, ShouldResemble, []PackageState{
				PackageState{
					PackageName: "test",
					InstanceID:  "0123456789abcdef00000123456789abcdef0000",
				},
				PackageState{
					PackageName: "test/pkg",
					InstanceID:  "0123456789abcdef00000123456789abcdef0000",
				},
				PackageState{
					PackageName: "test/pkg/123",
					InstanceID:  "0123456789abcdef00000123456789abcdef0000",
				},
				PackageState{
					PackageName: "test/pkg/456",
					InstanceID:  "0123456789abcdef00000123456789abcdef0000",
				},
			})
		})
	})
}

func TestRemoveDeployed(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		Convey("RemoveDeployed works with missing package", func() {
			err := RemoveDeployed(tempDir, "package/path")
			So(err, ShouldBeNil)
		})

		Convey("RemoveDeployed works", func() {
			// Deploy some instance (to keep it).
			inst := makeTestInstance("test/package/123", []File{
				makeTestFile("some/file/path1", "data a", false),
				makeTestFile("some/executable1", "data b", true),
			})
			_, err := DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)

			// Deploy another instance (to remove it).
			inst = makeTestInstance("test/package", []File{
				makeTestFile("some/file/path2", "data a", false),
				makeTestFile("some/executable2", "data b", true),
				makeTestSymlink("some/symlink", "executable"),
			})
			_, err = DeployInstance(tempDir, inst)
			So(err, ShouldBeNil)

			// Now remove the second package.
			err = RemoveDeployed(tempDir, "test/package")
			So(err, ShouldBeNil)

			// Verify the final state (only first package should survive).
			So(scanDir(tempDir), ShouldResemble, []string{
				".cipd/pkgs/package_123_Wnok5l4iFr/0123456789abcdef00000123456789abcdef0000/.cipdpkg/manifest.json",
				".cipd/pkgs/package_123_Wnok5l4iFr/0123456789abcdef00000123456789abcdef0000/some/executable1*",
				".cipd/pkgs/package_123_Wnok5l4iFr/0123456789abcdef00000123456789abcdef0000/some/file/path1",
				".cipd/pkgs/package_123_Wnok5l4iFr/_current:0123456789abcdef00000123456789abcdef0000",
				"some/executable1:../.cipd/pkgs/package_123_Wnok5l4iFr/_current/some/executable1",
				"some/file/path1:../../.cipd/pkgs/package_123_Wnok5l4iFr/_current/some/file/path1",
			})
		})
	})
}

////////////////////////////////////////////////////////////////////////////////

type testPackageInstance struct {
	packageName string
	instanceID  string
	files       []File
}

// makeTestInstance returns PackageInstance implementation with mocked guts.
func makeTestInstance(name string, files []File) *testPackageInstance {
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
	return &testPackageInstance{
		packageName: name,
		instanceID:  "0123456789abcdef00000123456789abcdef0000",
		files:       files,
	}
}

func (f *testPackageInstance) Close() error              { return nil }
func (f *testPackageInstance) PackageName() string       { return f.packageName }
func (f *testPackageInstance) InstanceID() string        { return f.instanceID }
func (f *testPackageInstance) Files() []File             { return f.files }
func (f *testPackageInstance) DataReader() io.ReadSeeker { panic("Not implemented") }

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
