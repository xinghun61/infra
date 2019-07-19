// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package fileset

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestSet(t *testing.T) {
	t.Parallel()

	Convey("Regular files", t, func(c C) {
		dir1 := newTempDir(c)
		dir1.touch("f1")
		dir1.mkdir("dir")
		dir1.touch("dir/a")
		dir1.mkdir("dir/empty")
		dir1.mkdir("dir/nested")
		dir1.touch("dir/nested/f")

		dir2 := newTempDir(c)
		dir2.touch("f2")
		dir2.mkdir("dir")
		dir2.touch("dir/b")

		dir3 := newTempDir(c)
		dir3.touch("f")

		s := &Set{}
		So(s.AddFromDisk(dir1.join(""), ""), ShouldBeNil)
		So(s.AddFromDisk(dir2.join(""), ""), ShouldBeNil)
		So(s.AddFromDisk(dir3.join(""), "dir/deep/"), ShouldBeNil)
		So(s.Add(File{Path: "some/deep/deep/path", Directory: true}), ShouldBeNil)
		So(s.Len(), ShouldEqual, 14)
		So(collect(s), ShouldResemble, []string{
			"D dir",
			"F dir/a",
			"F dir/b",
			"D dir/deep",
			"F dir/deep/f",
			"D dir/empty",
			"D dir/nested",
			"F dir/nested/f",
			"F f1",
			"F f2",
			"D some",
			"D some/deep",
			"D some/deep/deep",
			"D some/deep/deep/path",
		})
	})

	Convey("Reading body", t, func(c C) {
		s := &Set{}

		dir1 := newTempDir(c)
		dir1.put("f", "1", 0666)
		So(s.AddFromDisk(dir1.join(""), ""), ShouldBeNil)

		files := s.Files()
		So(files, ShouldHaveLength, 1)
		So(read(files[0]), ShouldEqual, "1")

		dir2 := newTempDir(c)
		dir2.put("f", "2", 0666)
		So(s.AddFromDisk(dir2.join(""), ""), ShouldBeNil)

		// Overwritten.
		files = s.Files()
		So(files, ShouldHaveLength, 1)
		So(read(files[0]), ShouldEqual, "2")
	})

	if runtime.GOOS != "windows" {
		Convey("Recognizes read-only", t, func(c C) {
			s := &Set{}

			dir := newTempDir(c)
			dir.put("ro", "", 0444)
			dir.put("rw", "", 0666)
			So(s.AddFromDisk(dir.join(""), ""), ShouldBeNil)

			files := s.Files()
			So(files, ShouldHaveLength, 2)
			So(files[0].Writable, ShouldBeFalse)
			So(files[1].Writable, ShouldBeTrue)
		})

		Convey("Recognizes executable", t, func(c C) {
			s := &Set{}

			dir := newTempDir(c)
			dir.put("n", "", 0666)
			dir.put("y", "", 0777)
			So(s.AddFromDisk(dir.join(""), ""), ShouldBeNil)

			files := s.Files()
			So(files, ShouldHaveLength, 2)
			So(files[0].Executable, ShouldBeFalse)
			So(files[1].Executable, ShouldBeTrue)
		})
	}

	Convey("Follows symlinks", t, func(c C) {
		dir := newTempDir(c)
		dir.touch("file")
		dir.mkdir("dir")
		dir.touch("dir/a")
		dir.mkdir("stage")
		dir.symlink("stage/filelink", "file")
		dir.symlink("stage/dirlink", "dir")
		dir.symlink("stage/broken", "broken") // skipped

		s := &Set{}
		So(s.AddFromDisk(dir.join("stage"), ""), ShouldBeNil)
		So(collect(s), ShouldResemble, []string{
			"D dirlink",
			"F dirlink/a",
			"F filelink",
		})
	})
}

func collect(s *Set) []string {
	out := []string{}
	s.Enumerate(func(f File) error {
		t := "F"
		if f.Directory {
			t = "D"
		}
		out = append(out, fmt.Sprintf("%s %s", t, f.Path))
		return nil
	})
	return out
}

func read(f File) string {
	r, err := f.Body()
	So(err, ShouldBeNil)
	defer r.Close()
	body, err := ioutil.ReadAll(r)
	So(err, ShouldBeNil)
	return string(body)
}

type tmpDir struct {
	p string
	c C
}

func newTempDir(c C) tmpDir {
	tmp, err := ioutil.TempDir("", "fileset_test")
	c.So(err, ShouldBeNil)
	c.Reset(func() { os.RemoveAll(tmp) })
	return tmpDir{tmp, c}
}

func (t tmpDir) join(p string) string {
	return filepath.Join(t.p, filepath.FromSlash(p))
}

func (t tmpDir) mkdir(p string) {
	t.c.So(os.MkdirAll(t.join(p), 0777), ShouldBeNil)
}

func (t tmpDir) put(p, data string, mode os.FileMode) {
	f, err := os.OpenFile(t.join(p), os.O_CREATE|os.O_WRONLY, mode)
	t.c.So(err, ShouldBeNil)
	_, err = f.Write([]byte(data))
	t.c.So(err, ShouldBeNil)
	t.c.So(f.Close(), ShouldBeNil)
}

func (t tmpDir) touch(p string) {
	t.put(p, "", 0666)
}

func (t tmpDir) symlink(name, target string) {
	So(os.Symlink(t.join(target), t.join(name)), ShouldBeNil)
}
