// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package local

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestToAbsPath(t *testing.T) {
	Convey("ToAbsPath works", t, func() {
		fs := tempFileSystem()
		p, err := fs.ToAbsPath(fs.Root())
		So(err, ShouldBeNil)
		So(p, ShouldEqual, fs.Root())

		p, err = fs.ToAbsPath(fs.join("abc"))
		So(err, ShouldBeNil)
		So(p, ShouldEqual, fs.join("abc"))

		_, err = fs.ToAbsPath(fs.join(".."))
		So(err, ShouldNotBeNil)

		_, err = fs.ToAbsPath(fs.join("../.."))
		So(err, ShouldNotBeNil)

		_, err = fs.ToAbsPath(fs.join("../abc"))
		So(err, ShouldNotBeNil)
	})
}

func TestEnsureDirectory(t *testing.T) {
	Convey("EnsureDirectory checks root", t, func() {
		fs := tempFileSystem()
		_, err := fs.EnsureDirectory(fs.join(".."))
		So(err, ShouldNotBeNil)
	})

	Convey("EnsureDirectory works", t, func() {
		fs := tempFileSystem()
		p, err := fs.EnsureDirectory(fs.join("x/../y/z"))
		So(err, ShouldBeNil)
		So(p, ShouldEqual, fs.join("y/z"))
		So(fs.isDir("y/z"), ShouldBeTrue)
		// Same one.
		_, err = fs.EnsureDirectory(fs.join("x/../y/z"))
		So(err, ShouldBeNil)
	})
}

func TestEnsureSymlink(t *testing.T) {
	Convey("EnsureSymlink checks root", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureSymlink(fs.join(".."), fs.Root()), ShouldNotBeNil)
	})

	Convey("ensureSymlink creates new symlink", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureSymlink(fs.join("symlink"), "target"), ShouldBeNil)
		So(fs.readLink("symlink"), ShouldEqual, "target")
	})

	Convey("ensureSymlink builds full path", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureSymlink(fs.join("a/b/c"), "target"), ShouldBeNil)
		So(fs.readLink("a/b/c"), ShouldEqual, "target")
	})

	Convey("ensureSymlink replaces existing one", t, func() {
		fs := tempFileSystem()
		// Replace with same one, then with another one.
		So(fs.EnsureSymlink(fs.join("symlink"), "target"), ShouldBeNil)
		So(fs.EnsureSymlink(fs.join("symlink"), "target"), ShouldBeNil)
		So(fs.EnsureSymlink(fs.join("symlink"), "another"), ShouldBeNil)
		So(fs.readLink("symlink"), ShouldEqual, "another")
	})
}

func TestEnsureFileGone(t *testing.T) {
	Convey("EnsureFileGone checks root", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureFileGone(fs.join("../abc")), ShouldNotBeNil)
	})

	Convey("EnsureFileGone works", t, func() {
		fs := tempFileSystem()
		fs.write("abc", "")
		So(fs.EnsureFileGone(fs.join("abc")), ShouldBeNil)
		So(fs.isMissing("abc"), ShouldBeTrue)
	})

	Convey("EnsureFileGone works with missing file", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureFileGone(fs.join("abc")), ShouldBeNil)
	})

	Convey("EnsureFileGone works with symlink", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureSymlink(fs.join("abc"), "target"), ShouldBeNil)
		So(fs.EnsureFileGone(fs.join("abc")), ShouldBeNil)
		So(fs.isMissing("abc"), ShouldBeTrue)
	})
}

func TestEnsureDirectoryGone(t *testing.T) {
	Convey("EnsureDirectoryGone checks root", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureDirectoryGone(fs.join("../abc")), ShouldNotBeNil)
	})

	Convey("EnsureDirectoryGone works", t, func() {
		fs := tempFileSystem()
		fs.write("dir/a/1", "")
		fs.write("dir/a/2", "")
		fs.write("dir/b/1", "")
		So(fs.EnsureDirectoryGone(fs.join("dir")), ShouldBeNil)
		So(fs.isMissing("dir"), ShouldBeTrue)
	})

	Convey("EnsureDirectoryGone works with missing dir", t, func() {
		fs := tempFileSystem()
		So(fs.EnsureDirectoryGone(fs.join("missing")), ShouldBeNil)
	})

}

func TestReplace(t *testing.T) {
	Convey("Replace checks root", t, func() {
		fs := tempFileSystem()
		So(fs.Replace(fs.join("../abc"), fs.join("def")), ShouldNotBeNil)
		fs.write("def", "")
		So(fs.Replace(fs.join("def"), fs.join("../abc")), ShouldNotBeNil)
	})

	Convey("Replace does nothing if oldpath == newpath", t, func() {
		fs := tempFileSystem()
		So(fs.Replace(fs.join("abc"), fs.join("abc/d/..")), ShouldBeNil)
	})

	Convey("Replace recognizes missing oldpath", t, func() {
		fs := tempFileSystem()
		So(fs.Replace(fs.join("missing"), fs.join("abc")), ShouldNotBeNil)
	})

	Convey("Replace creates file and dir if missing", t, func() {
		fs := tempFileSystem()
		fs.write("a/123", "")
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.isFile("b/c/d/"), ShouldBeTrue)
	})

	Convey("Replace replaces regular file with a file", t, func() {
		fs := tempFileSystem()
		fs.write("a/123", "xxx")
		fs.write("b/c/d", "yyy")
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d"), ShouldEqual, "xxx")
	})

	Convey("Replace replaces regular file with a dir", t, func() {
		fs := tempFileSystem()
		fs.write("a/123/456", "xxx")
		fs.write("b/c/d", "yyy")
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d/456"), ShouldEqual, "xxx")
	})

	Convey("Replace replaces empty dir with a file", t, func() {
		fs := tempFileSystem()
		fs.write("a/123", "xxx")
		_, err := fs.EnsureDirectory(fs.join("b/c/d"))
		So(err, ShouldBeNil)
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d"), ShouldEqual, "xxx")
	})

	Convey("Replace replaces empty dir with a dir", t, func() {
		fs := tempFileSystem()
		fs.write("a/123/456", "xxx")
		_, err := fs.EnsureDirectory(fs.join("b/c/d"))
		So(err, ShouldBeNil)
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d/456"), ShouldEqual, "xxx")
	})

	Convey("Replace replaces dir with a file", t, func() {
		fs := tempFileSystem()
		fs.write("a/123", "xxx")
		fs.write("b/c/d/456", "yyy")
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d"), ShouldEqual, "xxx")
	})

	Convey("Replace replaces dir with a dir", t, func() {
		fs := tempFileSystem()
		fs.write("a/123/456", "xxx")
		fs.write("b/c/d/456", "yyy")
		So(fs.Replace(fs.join("a/123"), fs.join("b/c/d")), ShouldBeNil)
		So(fs.isMissing("a/123"), ShouldBeTrue)
		So(fs.read("b/c/d/456"), ShouldEqual, "xxx")
	})
}

///////

// tempFileSystem returns FileSystem for tests built over a temp directory.
func tempFileSystem() *tempFileSystemImpl {
	tempDir, err := ioutil.TempDir("", "cipd_test")
	So(err, ShouldBeNil)
	Reset(func() { os.RemoveAll(tempDir) })
	return &tempFileSystemImpl{NewFileSystem(tempDir, nil)}
}

type tempFileSystemImpl struct {
	FileSystem
}

// join returns absolute path given a slash separated path relative to Root().
func (f *tempFileSystemImpl) join(path string) string {
	return filepath.Join(f.Root(), filepath.FromSlash(path))
}

// write creates a file at a given slash separated path relative to Root().
func (f *tempFileSystemImpl) write(rel string, data string) {
	abs := f.join(rel)
	err := os.MkdirAll(filepath.Dir(abs), 0777)
	So(err, ShouldBeNil)
	file, err := os.Create(abs)
	So(err, ShouldBeNil)
	file.WriteString(data)
	file.Close()
}

// read reads an existing file at a given slash separated path relative to Root().
func (f *tempFileSystemImpl) read(rel string) string {
	data, err := ioutil.ReadFile(f.join(rel))
	So(err, ShouldBeNil)
	return string(data)
}

// readLink reads a symlink at a given slash separated path relative to Root().
func (f *tempFileSystemImpl) readLink(rel string) string {
	val, err := os.Readlink(f.join(rel))
	So(err, ShouldBeNil)
	return val
}

// isMissing returns true if there's no file at a given slash separated path
// relative to Root().
func (f *tempFileSystemImpl) isMissing(rel string) bool {
	_, err := os.Stat(f.join(rel))
	return os.IsNotExist(err)
}

// isDir returns true if a file at a given slash separated path relative to
// Root() is a directory.
func (f *tempFileSystemImpl) isDir(rel string) bool {
	stat, err := os.Stat(f.join(rel))
	if err != nil {
		return false
	}
	return stat.IsDir()
}

// isFile returns true if a file at a given slash separated path relative to
// Root() is a file (not a directory).
func (f *tempFileSystemImpl) isFile(rel string) bool {
	stat, err := os.Stat(f.join(rel))
	if err != nil {
		return false
	}
	return !stat.IsDir()
}
