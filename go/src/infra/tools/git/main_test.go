// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"io/ioutil"
	"os"
	"testing"

	"golang.org/x/net/context"

	"infra/tools/git/state"

	"github.com/luci/luci-go/common/system/environ"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMain(t *testing.T) {
	t.Parallel()

	executable, err := os.Executable()
	if err != nil {
		t.Fatalf("failed to get self executable: %s", err)
	}

	Convey(`Using a test setup`, t, func() {
		c := context.Background()

		var env environ.Env
		runMain := func(c context.Context, args ...string) int {
			args = append([]string{executable}, args...)
			return mainImpl(c, args, env, bytes.NewReader(nil), ioutil.Discard, ioutil.Discard)
		}

		Convey(`When run in check mode, returns "1".`, func() {
			env.Set(gitWrapperCheckENV, executable)
			So(runMain(c), ShouldEqual, 1)
		})

		Convey(`Can run local Git (must be in PATH)`, func() {
			env = environ.System()
			systemGit, err := gitProbe.Locate(c, "", "", env)

			convey := Convey
			if err != nil {
				t.Logf("Cannot find system Git; skipping Git test: %s", err)
				convey = SkipConvey
			}

			convey(`With system Git`, func() {
				Convey(`"git version" returns 0.`, func() {
					So(runMain(c, "version"), ShouldEqual, 0)
				})

				Convey(`"git --clearly-an-invalid-flag" returns 129 (-1).`, func() {
					So(runMain(c, "--clearly-an-invalid-flag"), ShouldEqual, 129)
				})

				Convey(`Returns wrapper error code if we can't find Git.`, func() {
					env.Set("PATH", "")
					So(runMain(c, "version"), ShouldEqual, gitWrapperErrorReturnCode)
				})

				Convey(`Can use the cached Git path, if configured.`, func() {
					st := state.State{
						SelfPath: executable,
						GitPath:  systemGit,
					}
					env.Set(gitWrapperENV, st.ToENV())

					So(runMain(c, "version"), ShouldEqual, 0)
				})

				Convey(`Will ignore the cached Git path, if "self" is invalid.`, func() {
					st := state.State{
						SelfPath: "** DOES NOT EXIST **",
						GitPath:  systemGit,
					}
					env.Set(gitWrapperENV, st.ToENV())

					So(runMain(c, "version"), ShouldEqual, 0)
				})
			})
		})
	})
}
