// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cipd

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestScanFileSystem(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tempDir) })

		Convey("Scan empty dir works", func() {
			files, err := ScanFileSystem(tempDir)
			So(files, ShouldBeEmpty)
			So(err, ShouldBeNil)
		})

		Convey("Discovering single file works", func() {
			writeFile(tempDir, "single_file", "12345", 0666)
			files, err := ScanFileSystem(tempDir)
			So(len(files), ShouldEqual, 1)
			So(err, ShouldBeNil)

			file := files[0]
			So(file.Name(), ShouldEqual, "single_file")
			So(file.Size(), ShouldEqual, uint64(5))
			So(file.Executable(), ShouldBeFalse)

			r, err := file.Open()
			if r != nil {
				defer r.Close()
			}
			So(err, ShouldBeNil)
			buf, err := ioutil.ReadAll(r)
			So(buf, ShouldResemble, []byte("12345"))
			So(err, ShouldBeNil)
		})

		Convey("Discovering single executable file works", func() {
			writeFile(tempDir, "single_file", "12345", 0766)
			files, err := ScanFileSystem(tempDir)
			So(len(files), ShouldEqual, 1)
			So(err, ShouldBeNil)
			file := files[0]
			So(file.Executable(), ShouldBeTrue)
		})

		Convey("Discovering absolute symlink outside of package works", func() {
			// Pick a path outside of tempDir. Picking '/' wont work on Windows, so
			// just use a parent directory.
			target := filepath.Dir(tempDir)
			writeSymlink(tempDir, "abs_symlink", target)
			files, err := ScanFileSystem(tempDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			ensureSymlinkTarget(files[0], filepath.ToSlash(target))
		})

		Convey("Discovering absolute symlink inside of package works", func() {
			writeSymlink(tempDir, "a/b1/abs_symlink", filepath.Join(tempDir, "a", "b2", "c"))
			files, err := ScanFileSystem(tempDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			ensureSymlinkTarget(files[0], "../b2/c")
		})

		Convey("Discovering allowed relative symlink works", func() {
			writeSymlink(tempDir, "a/b1/rel_symlink", filepath.FromSlash("../def"))
			files, err := ScanFileSystem(tempDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			ensureSymlinkTarget(files[0], "../def")
		})

		Convey("Relative symlink to outside of package are forbidden", func() {
			writeSymlink(tempDir, "a/b1/rel_symlink", filepath.FromSlash("../../.."))
			_, err := ScanFileSystem(tempDir)
			So(err, ShouldNotBeNil)
		})

		Convey("Enumerating subdirectories", func() {
			writeFile(tempDir, "a", "", 0666)
			writeFile(tempDir, "b", "", 0666)
			writeFile(tempDir, "1/a", "", 0666)
			writeFile(tempDir, "1/b", "", 0666)
			writeFile(tempDir, "1/2/a", "", 0666)
			files, err := ScanFileSystem(tempDir)
			So(len(files), ShouldEqual, 5)
			So(err, ShouldBeNil)
			names := []string{}
			for _, f := range files {
				names = append(names, f.Name())
			}
			// Order matters. Slashes matters.
			So(names, ShouldResemble, []string{
				"1/2/a",
				"1/a",
				"1/b",
				"a",
				"b",
			})
		})

		Convey("Empty subdirectories are skipped", func() {
			mkDir(tempDir, "a")
			mkDir(tempDir, "1/2/3")
			mkDir(tempDir, "1/c")
			writeFile(tempDir, "1/d/file", "1234", 0666)
			files, err := ScanFileSystem(tempDir)
			So(len(files), ShouldEqual, 1)
			So(err, ShouldBeNil)
			So(files[0].Name(), ShouldEqual, "1/d/file")
		})
	})
}

func mkDir(root string, path string) {
	abs := filepath.Join(root, filepath.FromSlash(path))
	err := os.MkdirAll(abs, 0777)
	if err != nil {
		panic("Failed to create a directory under temp directory")
	}
}

func writeFile(root string, path string, data string, mode os.FileMode) {
	abs := filepath.Join(root, filepath.FromSlash(path))
	os.MkdirAll(filepath.Dir(abs), 0777)
	err := ioutil.WriteFile(abs, []byte(data), mode)
	if err != nil {
		panic("Failed to write a temp file")
	}
}

func writeSymlink(root string, path string, target string) {
	abs := filepath.Join(root, filepath.FromSlash(path))
	os.MkdirAll(filepath.Dir(abs), 0777)
	err := os.Symlink(target, abs)
	if err != nil {
		panic("Failed to create symlink")
	}
}

func ensureSymlinkTarget(file File, target string) {
	So(file.Symlink(), ShouldBeTrue)
	discoveredTarget, err := file.SymlinkTarget()
	So(err, ShouldBeNil)
	So(discoveredTarget, ShouldEqual, target)
}

func TestFileSystemDestination(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		destDir := filepath.Join(tempDir, "dest")
		So(err, ShouldBeNil)
		dest := NewFileSystemDestination(destDir)
		Reset(func() { os.RemoveAll(tempDir) })

		writeFileToDest := func(name string, executable bool, data string) {
			writer, err := dest.CreateFile(name, executable)
			if writer != nil {
				defer writer.Close()
			}
			So(err, ShouldBeNil)
			_, err = writer.Write([]byte(data))
			So(err, ShouldBeNil)
		}

		writeSymlinkToDest := func(name string, target string) {
			err := dest.CreateSymlink(name, target)
			So(err, ShouldBeNil)
		}

		Convey("Empty success write works", func() {
			So(dest.Begin(), ShouldBeNil)
			So(dest.End(true), ShouldBeNil)

			// Should create a new directory.
			stat, err := os.Stat(destDir)
			So(err, ShouldBeNil)
			So(stat.IsDir(), ShouldBeTrue)

			// And it should be empty.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 0)
		})

		Convey("Empty failed write works", func() {
			So(dest.Begin(), ShouldBeNil)
			So(dest.End(false), ShouldBeNil)

			// Doesn't create a directory.
			_, err := os.Stat(destDir)
			So(os.IsNotExist(err), ShouldBeTrue)
		})

		Convey("Double begin or double end fails", func() {
			So(dest.Begin(), ShouldBeNil)
			So(dest.Begin(), ShouldNotBeNil)
			So(dest.End(true), ShouldBeNil)
			So(dest.End(true), ShouldNotBeNil)
		})

		Convey("CreateFile works only when destination is open", func() {
			wr, err := dest.CreateFile("testing", true)
			So(wr, ShouldBeNil)
			So(err, ShouldNotBeNil)
		})

		Convey("CreateFile rejects invalid relative paths", func() {
			So(dest.Begin(), ShouldBeNil)
			defer dest.End(true)

			// Rel path that is still inside the package is ok.
			wr, err := dest.CreateFile("a/b/c/../../../d", false)
			So(err, ShouldBeNil)
			wr.Close()

			// Rel path pointing outside is forbidden.
			_, err = dest.CreateFile("a/b/c/../../../../d", false)
			So(err, ShouldNotBeNil)
		})

		Convey("CreateSymlink rejects invalid relative paths", func() {
			So(dest.Begin(), ShouldBeNil)
			defer dest.End(true)

			// Rel symlink to a file inside the destination is OK.
			So(dest.CreateSymlink("a/b/c", "../.."), ShouldBeNil)
			// Rel symlink to a file outside -> error.
			So(dest.CreateSymlink("a/b/c", "../../.."), ShouldNotBeNil)
		})

		Convey("Committing bunch of files works", func() {
			So(dest.Begin(), ShouldBeNil)
			writeFileToDest("a", false, "a data")
			writeFileToDest("exe", true, "exe data")
			writeFileToDest("dir/c", false, "dir/c data")
			writeFileToDest("dir/dir/d", false, "dir/dir/c data")
			writeSymlinkToDest("abs_symlink", filepath.FromSlash(tempDir))
			writeSymlinkToDest("dir/dir/rel_symlink", "../../a")
			So(dest.End(true), ShouldBeNil)

			// Ensure everything is there.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			names := []string{}
			for _, f := range files {
				names = append(names, f.Name())
			}
			So(names, ShouldResemble, []string{
				"a",
				"abs_symlink",
				"dir/c",
				"dir/dir/d",
				"dir/dir/rel_symlink",
				"exe",
			})

			// Ensure data is valid (check first file only).
			r, err := files[0].Open()
			if r != nil {
				defer r.Close()
			}
			So(err, ShouldBeNil)
			data, err := ioutil.ReadAll(r)
			So(err, ShouldBeNil)
			So(data, ShouldResemble, []byte("a data"))

			// Ensure file mode is valid.
			So(files[5].Name(), ShouldEqual, "exe")
			So(files[5].Executable(), ShouldBeTrue)

			// Ensure absolute symlink if valid.
			So(files[1].Name(), ShouldEqual, "abs_symlink")
			ensureSymlinkTarget(files[1], filepath.FromSlash(tempDir))

			// Ensure relative symlink is valid.
			So(files[4].Name(), ShouldEqual, "dir/dir/rel_symlink")
			ensureSymlinkTarget(files[4], "../../a")

			// Ensure no temp files left.
			allFiles, err := ScanFileSystem(tempDir)
			So(len(allFiles), ShouldEqual, len(files))
		})

		Convey("Rolling back bunch of files works", func() {
			So(dest.Begin(), ShouldBeNil)
			writeFileToDest("a", false, "a data")
			writeFileToDest("dir/c", false, "dir/c data")
			writeSymlinkToDest("dir/d", "c")
			So(dest.End(false), ShouldBeNil)

			// No dest directory.
			_, err := os.Stat(destDir)
			So(os.IsNotExist(err), ShouldBeTrue)

			// Ensure no temp files left.
			allFiles, err := ScanFileSystem(tempDir)
			So(len(allFiles), ShouldEqual, 0)
		})

		Convey("Overwriting a directory works", func() {
			// Create dest directory manually with some stuff.
			err := os.Mkdir(destDir, 0777)
			So(err, ShouldBeNil)
			err = ioutil.WriteFile(filepath.Join(destDir, "data"), []byte("data"), 0666)
			So(err, ShouldBeNil)

			// Now deploy something to it.
			So(dest.Begin(), ShouldBeNil)
			writeFileToDest("a", false, "a data")
			writeSymlinkToDest("b", "a")
			So(dest.End(true), ShouldBeNil)

			// Overwritten.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 2)
			So(files[0].Name(), ShouldEqual, "a")
			So(files[1].Name(), ShouldEqual, "b")
		})

		Convey("Not overwriting a directory works", func() {
			// Create dest directory manually with some stuff.
			err := os.Mkdir(destDir, 0777)
			So(err, ShouldBeNil)
			err = ioutil.WriteFile(filepath.Join(destDir, "data"), []byte("data"), 0666)
			So(err, ShouldBeNil)

			// Now attempt deploy something to it, but roll back.
			So(dest.Begin(), ShouldBeNil)
			writeFileToDest("a", false, "a data")
			writeSymlinkToDest("b", "a")
			So(dest.End(false), ShouldBeNil)

			// Kept as is.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			So(files[0].Name(), ShouldEqual, "data")
		})

		Convey("Opening file twice fails", func() {
			So(dest.Begin(), ShouldBeNil)
			writeFileToDest("a", false, "a data")
			w, err := dest.CreateFile("a", false)
			So(w, ShouldBeNil)
			So(err, ShouldNotBeNil)
			So(dest.End(true), ShouldBeNil)
		})

		Convey("End with opened files fail", func() {
			So(dest.Begin(), ShouldBeNil)
			w, err := dest.CreateFile("a", false)
			So(w, ShouldNotBeNil)
			So(err, ShouldBeNil)
			So(dest.End(true), ShouldNotBeNil)
			w.Close()
			So(dest.End(true), ShouldBeNil)
		})
	})
}
