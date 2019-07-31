// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestLoadAndResolve(t *testing.T) {
	t.Parallel()

	Convey("With temp dir", t, func() {
		tmpDir, err := ioutil.TempDir("", "builder_test")
		So(err, ShouldBeNil)
		Reset(func() { os.RemoveAll(tmpDir) })

		put := func(path, body string) string {
			fp := filepath.Join(tmpDir, filepath.FromSlash(path))
			So(ioutil.WriteFile(fp, []byte(body), 0666), ShouldBeNil)
			return fp
		}

		Convey("Works", func() {
			body, err := LoadAndResolve(
				put("Dockerfile", `
FROM ubuntu AS builder # blah
FROM scratch
FROM ubuntu:xenial
`),
				put("pins.yaml", `pins:
- image: ubuntu
  tag: latest
  digest: sha256:123
- image: ubuntu
  tag: xenial
  digest: sha256:456
`),
			)
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, `
FROM ubuntu@sha256:123 AS builder # blah
FROM scratch
FROM ubuntu@sha256:456
`)
		})

		Convey("No pins, but using digests already", func() {
			body, err := LoadAndResolve(
				put("Dockerfile", `
FROM ubuntu@sha256:123 AS builder # blah
FROM scratch
FROM ubuntu@sha256:456
`),
				"",
			)
			So(err, ShouldBeNil)
			So(string(body), ShouldEqual, `
FROM ubuntu@sha256:123 AS builder # blah
FROM scratch
FROM ubuntu@sha256:456
`)
		})

		Convey("No pins and using a tag", func() {
			_, err := LoadAndResolve(
				put("Dockerfile", `FROM ubuntu`),
				"",
			)
			So(err, ShouldErrLike, `line 1: resolving "ubuntu:latest": not using pins YAML, the Dockerfile must use @<digest> refs`)
		})

		Convey("Unknown tag", func() {
			_, err := LoadAndResolve(
				put("Dockerfile", `FROM ubuntu`),
				put("pins.yaml", `{"pins": [{"image": "zzz", "digest": "zzz"}]}`),
			)
			So(err, ShouldErrLike, `line 1: resolving "ubuntu:latest": no such pinned <image>:<tag> combination in pins YAML`)
		})
	})
}
