// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/testing/testfs"

	. "github.com/luci/luci-go/common/testing/assertions"
	. "github.com/smartystreets/goconvey/convey"
)

// TestFindSystemGit tests the ability to locate the "git" command in PATH.
//
// This test is NOT parallel-safe, as it modifies the process-global PATH
// environment variable.
func TestSystemProbe(t *testing.T) {
	// Protect absolutely against PATH modifications in this test.
	origPATH := os.Getenv("PATH")
	defer func() {
		if err := os.Setenv("PATH", origPATH); err != nil {
			t.Fatalf("Failed to restore PATH: %s", err)
		}
	}()

	var selfEXESuffix, otherEXESuffix string
	if runtime.GOOS == "windows" {
		selfEXESuffix = ".exe"
		otherEXESuffix = ".bat"
	}

	Convey(`With a fake PATH setup`, t, testfs.MustWithTempDir(t, "git_find", func(tdir string) {
		c := context.Background()

		createExecutable := func(relPath string) (dir string, path string) {
			path = filepath.Join(tdir, filepath.FromSlash(relPath))
			dir = filepath.Dir(path)
			if err := os.MkdirAll(dir, 0755); err != nil {
				t.Fatalf("Failed to create base directory [%s]: %s", dir, err)
			}
			if err := ioutil.WriteFile(path, []byte("fake"), 0755); err != nil {
				t.Fatalf("Failed to create executable: %s", err)
			}
			return
		}

		// Construct a fake filesystem rooted in "tdir".
		var (
			selfDir, selfGit = createExecutable("self/git" + selfEXESuffix)
			fooDir, fooGit   = createExecutable("foo/git" + otherEXESuffix)
			wrapperDir, _    = createExecutable("wrapper/git" + otherEXESuffix)
			brokenDir, _     = createExecutable("broken/git" + otherEXESuffix)
			otherDir, _      = createExecutable("other/not_git")
			nonexistDir      = filepath.Join(tdir, "nonexist")
			nonexistGit      = filepath.Join(nonexistDir, "git"+otherEXESuffix)
		)

		// Set up a base probe.
		wrapperChecks := 0
		probe := SystemProbe{
			Target: "git",

			testRunCommand: func(cmd *exec.Cmd) (int, error) {
				wrapperChecks++
				switch filepath.Dir(cmd.Path) {
				case wrapperDir, selfDir:
					return 1, nil
				case brokenDir:
					return 0, errors.New("broken")
				default:
					return 0, nil
				}
			},
		}

		env := environ.System()
		setPATH := func(v ...string) {
			path := strings.Join(v, string(os.PathListSeparator))
			env.Set("PATH", path)
		}

		Convey(`Can identify the next Git when it follows self in PATH.`, func() {
			setPATH(selfDir, selfDir, fooDir, wrapperDir, otherDir, nonexistDir)

			git, err := probe.Locate(c, selfGit, "", env)
			So(err, ShouldBeNil)
			So(git, shouldBeSameFileAs, fooGit)
			So(wrapperChecks, ShouldEqual, 1)
		})

		Convey(`Can identify the next Git when it precedes self in PATH.`, func() {
			setPATH(fooDir, selfDir, wrapperDir, otherDir, nonexistDir)

			git, err := probe.Locate(c, selfGit, "", env)
			So(err, ShouldBeNil)
			So(git, shouldBeSameFileAs, fooGit)
			So(wrapperChecks, ShouldEqual, 1)
		})

		Convey(`Can identify the next Git when self does not exist.`, func() {
			setPATH(wrapperDir, selfDir, wrapperDir, otherDir, nonexistDir, fooDir)

			git, err := probe.Locate(c, nonexistGit, "", env)
			So(err, ShouldBeNil)
			So(git, shouldBeSameFileAs, fooGit)
			So(wrapperChecks, ShouldEqual, 3)
		})

		Convey(`With PATH setup pointing to a wrapper, self, and then the system Git`, func() {
			// NOTE: wrapperDir is repeated, but it will only count towards one check,
			// since we cache checks on a per-directory basis.
			setPATH(wrapperDir, wrapperDir, selfDir, otherDir, fooDir, nonexistDir)

			Convey(`Will prefer the cached value.`, func() {
				git, err := probe.Locate(c, selfGit, fooGit, env)
				So(err, ShouldBeNil)
				So(git, shouldBeSameFileAs, fooGit)
				So(wrapperChecks, ShouldEqual, 0)
			})

			Convey(`Will ignore the cached value if it is self.`, func() {
				git, err := probe.Locate(c, selfGit, selfGit, env)
				So(err, ShouldBeNil)
				So(git, shouldBeSameFileAs, fooGit)
				So(wrapperChecks, ShouldEqual, 2)
			})

			Convey(`Will ignore the cached value if it does not exist.`, func() {
				git, err := probe.Locate(c, selfGit, nonexistGit, env)
				So(err, ShouldBeNil)
				So(git, shouldBeSameFileAs, fooGit)
				So(wrapperChecks, ShouldEqual, 2)
			})

			Convey(`Will skip the wrapper and identify the system Git.`, func() {
				git, err := probe.Locate(c, selfGit, "", env)
				So(err, ShouldBeNil)
				So(git, shouldBeSameFileAs, fooGit)
				So(wrapperChecks, ShouldEqual, 2)
			})
		})

		Convey(`Will skip everything if the wrapper check fails.`, func() {
			setPATH(wrapperDir, brokenDir, selfDir, otherDir, fooDir, nonexistDir)

			git, err := probe.Locate(c, selfGit, "", env)
			So(err, ShouldBeNil)
			So(git, shouldBeSameFileAs, fooGit)
			So(wrapperChecks, ShouldEqual, 3)
		})

		Convey(`Will fail if cannot find another Git in PATH.`, func() {
			setPATH(selfDir, otherDir, nonexistDir)

			_, err := probe.Locate(c, selfGit, "", env)
			So(err, ShouldErrLike, "could not find target in system")
			So(wrapperChecks, ShouldEqual, 0)
		})

		Convey(`When a symlink is created`, func() {
			conveyFn := Convey
			if err := os.Symlink(selfGit, filepath.Join(otherDir, filepath.Base(selfGit))); err != nil {
				t.Logf("Failed to create symlink; skipping symlink test: %s", err)
				conveyFn = SkipConvey
			}

			conveyFn(`Will ignore symlink because it's the same file.`, func() {
				setPATH(selfDir, otherDir, fooDir, wrapperDir)
				git, err := probe.Locate(c, selfGit, "", env)
				So(err, ShouldBeNil)
				So(git, shouldBeSameFileAs, fooGit)
				So(wrapperChecks, ShouldEqual, 1)
			})
		})
	}))
}

func shouldBeSameFileAs(actual interface{}, expected ...interface{}) string {
	aPath, ok := actual.(string)
	if !ok {
		return "actual must be a path string"
	}

	if len(expected) != 1 {
		return "exactly one expected path string must be provided"
	}
	expPath, ok := expected[0].(string)
	if !ok {
		return "expected must be a path string"
	}

	aSt, err := os.Stat(aPath)
	if err != nil {
		return fmt.Sprintf("failed to stat actual [%s]: %s", aPath, err)
	}
	expSt, err := os.Stat(expPath)
	if err != nil {
		return fmt.Sprintf("failed to stat expected [%s]: %s", expPath, err)
	}

	if !os.SameFile(aSt, expSt) {
		return fmt.Sprintf("[%s] is not the same file as [%s]", expPath, aPath)
	}
	return ""
}
