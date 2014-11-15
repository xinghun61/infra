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

func TestFileSystemDestination(t *testing.T) {
	Convey("Given a temp directory", t, func() {
		tempDir, err := ioutil.TempDir("", "cipd_test")
		destDir := filepath.Join(tempDir, "dest")
		So(err, ShouldBeNil)
		dest := NewFileSystemDestination(destDir)
		Reset(func() { os.RemoveAll(tempDir) })

		writeToDest := func(name string, executable bool, data string) {
			writer, err := dest.CreateFile(name, executable)
			if writer != nil {
				defer writer.Close()
			}
			So(err, ShouldBeNil)
			_, err = writer.Write([]byte(data))
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

		Convey("Committing bunch of files works", func() {
			So(dest.Begin(), ShouldBeNil)
			writeToDest("a", false, "a data")
			writeToDest("exe", true, "exe data")
			writeToDest("dir/c", false, "dir/c data")
			writeToDest("dir/dir/d", false, "dir/dir/c data")
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
				"dir/c",
				"dir/dir/d",
				"exe",
			})

			// Ensure data is valid.
			r, err := files[0].Open()
			if r != nil {
				defer r.Close()
			}
			So(err, ShouldBeNil)
			data, err := ioutil.ReadAll(r)
			So(err, ShouldBeNil)
			So(data, ShouldResemble, []byte("a data"))

			// Ensure file mode is valid.
			So(files[3].Name(), ShouldEqual, "exe")
			So(files[3].Executable(), ShouldBeTrue)

			// Ensure no temp files left.
			allFiles, err := ScanFileSystem(tempDir)
			So(len(allFiles), ShouldEqual, len(files))
		})

		Convey("Rolling back bunch of files works", func() {
			So(dest.Begin(), ShouldBeNil)
			writeToDest("a", false, "a data")
			writeToDest("dir/c", false, "dir/c data")
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
			writeToDest("a", false, "a data")
			So(dest.End(true), ShouldBeNil)

			// Overwritten.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			So(files[0].Name(), ShouldEqual, "a")
		})

		Convey("Not overwriting a directory works", func() {
			// Create dest directory manually with some stuff.
			err := os.Mkdir(destDir, 0777)
			So(err, ShouldBeNil)
			err = ioutil.WriteFile(filepath.Join(destDir, "data"), []byte("data"), 0666)
			So(err, ShouldBeNil)

			// Now attempt deploy something to it, but roll back.
			So(dest.Begin(), ShouldBeNil)
			writeToDest("a", false, "a data")
			So(dest.End(false), ShouldBeNil)

			// Kept as it.
			files, err := ScanFileSystem(destDir)
			So(err, ShouldBeNil)
			So(len(files), ShouldEqual, 1)
			So(files[0].Name(), ShouldEqual, "data")
		})

		Convey("Opening file twice fails", func() {
			So(dest.Begin(), ShouldBeNil)
			writeToDest("a", false, "a data")
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
