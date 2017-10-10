// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/auth/authtest"
	"go.chromium.org/luci/common/system/environ"

	. "github.com/smartystreets/goconvey/convey"
)

func init() {
	isRunningUnitTests = true // see git.go
}

func TestGit(t *testing.T) {
	t.Parallel()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skipf("git is not present: %s", err)
	}

	Convey("checkoutRepository", t, func() {
		fakeAuth := authtest.FakeContext{}
		ctx, err := fakeAuth.Start(context.Background())
		So(err, ShouldBeNil)
		defer fakeAuth.Stop(ctx)

		tmp, err := ioutil.TempDir("", "")
		So(err, ShouldBeNil)
		defer os.RemoveAll(tmp)

		env := environ.System()

		srcRepo := filepath.Join(tmp, "src")
		So(os.Mkdir(srcRepo, 0777), ShouldBeNil)
		_, err = runGit(ctx, env, srcRepo, "init")
		So(err, ShouldBeNil)

		So(ioutil.WriteFile(filepath.Join(srcRepo, "a"), []byte("a"), 0777), ShouldBeNil)

		_, err = runGit(ctx, env, srcRepo, "add", "-A")
		So(err, ShouldBeNil)

		_, err = runGit(ctx, env, srcRepo, "commit", "-m", "c1")
		So(err, ShouldBeNil)

		So(ioutil.WriteFile(filepath.Join(srcRepo, "b"), []byte("b"), 0777), ShouldBeNil)

		_, err = runGit(ctx, env, srcRepo, "add", "-A")
		So(err, ShouldBeNil)

		_, err = runGit(ctx, env, srcRepo, "commit", "-m", "c2")
		So(err, ShouldBeNil)

		destRepo := filepath.Join(tmp, "dest")
		_, err = checkoutRepository(ctx, env, destRepo, srcRepo, "refs/heads/master")
		So(err, ShouldBeNil)

		out, err := runGit(ctx, env, destRepo, "log", "--format=%s")
		So(err, ShouldBeNil)
		So(strings.Split(strings.TrimSpace(string(out)), "\n"), ShouldResemble, []string{"c2", "c1"})
	})
}
