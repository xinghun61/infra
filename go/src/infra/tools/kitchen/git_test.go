// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGit(t *testing.T) {
	t.Parallel()
	if _, err := exec.LookPath("git"); err != nil {
		t.Skipf("git is not present: %s", err)
	}

	Convey("checkoutRepository", t, func() {
		ctx := context.Background()
		tmp, err := ioutil.TempDir("", "")
		So(err, ShouldBeNil)
		defer os.RemoveAll(tmp)

		srcRepo := filepath.Join(tmp, "src")
		So(os.Mkdir(srcRepo, 0777), ShouldBeNil)
		_, err = runGit(ctx, srcRepo, "init")
		So(err, ShouldBeNil)

		So(ioutil.WriteFile(filepath.Join(srcRepo, "a"), []byte("a"), 0777), ShouldBeNil)

		_, err = runGit(ctx, srcRepo, "add", "-A")
		So(err, ShouldBeNil)

		_, err = runGit(ctx, srcRepo, "commit", "-m", "c1")
		So(err, ShouldBeNil)

		So(ioutil.WriteFile(filepath.Join(srcRepo, "b"), []byte("b"), 0777), ShouldBeNil)

		_, err = runGit(ctx, srcRepo, "add", "-A")
		So(err, ShouldBeNil)

		_, err = runGit(ctx, srcRepo, "commit", "-m", "c2")
		So(err, ShouldBeNil)

		destRepo := filepath.Join(tmp, "dest")
		_, err = checkoutRepository(ctx, destRepo, srcRepo, "refs/heads/master")
		So(err, ShouldBeNil)

		out, err := runGit(ctx, destRepo, "log", "--format=%s")
		So(err, ShouldBeNil)
		So(strings.Split(strings.TrimSpace(string(out)), "\n"), ShouldResemble, []string{"c2", "c1"})
	})
}
