// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
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
		gitOutput(ctx, srcRepo, "init")
		So(ioutil.WriteFile(filepath.Join(srcRepo, "a"), []byte("a"), 0777), ShouldBeNil)
		gitOutput(ctx, srcRepo, "add", "-A")
		gitOutput(ctx, srcRepo, "commit", "-m", "c1")
		So(ioutil.WriteFile(filepath.Join(srcRepo, "b"), []byte("b"), 0777), ShouldBeNil)
		gitOutput(ctx, srcRepo, "add", "-A")
		gitOutput(ctx, srcRepo, "commit", "-m", "c2")

		destRepo := filepath.Join(tmp, "dest")
		So(checkoutRepository(ctx, destRepo, srcRepo, "refs/heads/master"), ShouldBeNil)

		So(
			strings.Split(strings.TrimSpace(gitOutput(ctx, destRepo, "log", "--format=%s")), "\n"),
			ShouldResemble,
			[]string{"c2", "c1"})
	})
}

func gitOutput(c context.Context, workdir string, args ...string) string {
	cmd := git(c, workdir, args...)
	buf := &bytes.Buffer{}
	cmd.Stdout = buf
	So(cmd.Run(), ShouldBeNil)
	return buf.String()
}
