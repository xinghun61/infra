// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// OS-agnostic helper functions which are called from run().

package firstrun

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

type fakeFileInfo struct {
	name    string
	size    int64
	mode    os.FileMode
	modTime time.Time
	isDir   bool
}

func (f fakeFileInfo) Name() string       { return f.name }
func (f fakeFileInfo) Size() int64        { return f.size }
func (f fakeFileInfo) Mode() os.FileMode  { return f.mode }
func (f fakeFileInfo) ModTime() time.Time { return f.modTime }
func (f fakeFileInfo) IsDir() bool        { return f.isDir }
func (f fakeFileInfo) Sys() interface{}   { return nil }

func TestCheckNotInstalled(t *testing.T) {
	t.Parallel()
	Convey("When checking that cr isn't already installed", t, func() {
		Convey("an empty $PATH results in an error", func() {
			getenv = func(s string) string { return "" }
			path, err := firstrunCheckNotInstalled()
			So(path, ShouldEqual, "")
			So(err, ShouldNotBeNil)
		})

		Convey("paths not ending in cr/bin are ignored", func() {
			getenv = func(s string) string {
				paths := []string{
					filepath.Join("foo", "bar"),
					filepath.Join("foo", "cr", "bin", "bar"),
				}
				return strings.Join(paths, string(os.PathListSeparator))
			}
			path, err := firstrunCheckNotInstalled()
			So(path, ShouldEqual, "")
			So(err, ShouldBeNil)
		})

		Convey("multiple candidates are all checked", func() {
			getenv = func(s string) string {
				paths := []string{
					filepath.Join("foo", "cr", "bin"),
					filepath.Join("foo", "bar", "cr", "bin"),
				}
				return strings.Join(paths, string(os.PathListSeparator))
			}

			Convey("and missing executables are handled", func() {
				stat = func(s string) (os.FileInfo, error) {
					return nil, os.ErrNotExist
				}
				path, err := firstrunCheckNotInstalled()
				So(path, ShouldEqual, "")
				So(err, ShouldBeNil)
			})

			Convey("and non-executables are ignored", func() {
				stat = func(s string) (os.FileInfo, error) {
					return fakeFileInfo{executableName, 64, 0666, time.Now(), false}, nil
				}
				path, err := firstrunCheckNotInstalled()
				So(err, ShouldBeNil)
				So(path, ShouldEqual, "")
			})

			Convey("and the only executable is returned", func() {
				stat = func(s string) (os.FileInfo, error) {
					if strings.Contains(s, "bar") {
						return fakeFileInfo{executableName, 64, 0777, time.Now(), false}, nil
					}
					return fakeFileInfo{executableName, 64, 0666, time.Now(), false}, nil
				}
				path, err := firstrunCheckNotInstalled()
				So(path, ShouldEqual, filepath.Join("foo", "bar", "cr", "bin", executableName))
				So(err, ShouldBeNil)
			})

			Convey("and the first executable is returned", func() {
				stat = func(s string) (os.FileInfo, error) {
					return fakeFileInfo{executableName, 64, 0777, time.Now(), false}, nil
				}
				path, err := firstrunCheckNotInstalled()
				So(path, ShouldEqual, filepath.Join("foo", "cr", "bin", executableName))
				So(err, ShouldBeNil)
			})

			Convey("and errors are propagated forward", func() {
				stat = func(s string) (os.FileInfo, error) {
					if strings.Contains(s, "bar") {
						return fakeFileInfo{executableName, 64, 0666, time.Now(), false}, nil
					}
					return nil, errors.New("some crazy error")
				}
				path, err := firstrunCheckNotInstalled()
				So(path, ShouldEqual, "")
				So(err, ShouldResemble, errors.New("some crazy error"))
			})
		})
	})
}
