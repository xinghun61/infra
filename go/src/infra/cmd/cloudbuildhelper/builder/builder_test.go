// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package builder

import (
	"context"
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	"infra/cmd/cloudbuildhelper/manifest"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuilder(t *testing.T) {
	t.Parallel()

	ctx := context.Background()

	Convey("With temp dir", t, func() {
		tmpDir, err := ioutil.TempDir("", "builder_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tmpDir) })

		put := func(path, body string) {
			fp := filepath.Join(tmpDir, filepath.FromSlash(path))
			So(ioutil.WriteFile(fp, []byte(body), 0666), ShouldBeNil)
		}

		Convey("Build ContextDir only", func() {
			b, err := New()
			So(err, ShouldBeNil)

			put("f1", "file 1")
			put("f2", "file 2")

			out, err := b.Build(ctx, &manifest.Manifest{
				ContextDir: tmpDir,
			})
			So(err, ShouldBeNil)
			So(out.Files(), ShouldHaveLength, 2)

			So(b.Close(), ShouldBeNil)
			So(b.Close(), ShouldBeNil) // idempotent
		})
	})
}
