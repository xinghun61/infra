// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestPins(t *testing.T) {
	t.Parallel()

	Convey("Works", t, func() {
		p, err := ReadPins(strings.NewReader(`{"pins": [
      {"image": "xxx", "digest": "sha256:123"},
      {"image": "library/yyy", "tag": "old", "digest": "sha256:456"},
      {"image": "gcr.io/example/zzz", "tag": "1.2.3", "digest": "sha256:789"}
    ]}`))
		So(err, ShouldBeNil)

		r := p.Resolver()

		d, err := r.ResolveTag("xxx", "")
		So(err, ShouldBeNil)
		So(d, ShouldEqual, "sha256:123")

		// The same exact pin.
		d, err = r.ResolveTag("library/xxx", "latest")
		So(err, ShouldBeNil)
		So(d, ShouldEqual, "sha256:123")

		// And this one too.
		d, err = r.ResolveTag("docker.io/library/xxx", "latest")
		So(err, ShouldBeNil)
		So(d, ShouldEqual, "sha256:123")

		d, err = r.ResolveTag("yyy", "old")
		So(err, ShouldBeNil)
		So(d, ShouldEqual, "sha256:456")

		d, err = r.ResolveTag("gcr.io/example/zzz", "1.2.3")
		So(err, ShouldBeNil)
		So(d, ShouldEqual, "sha256:789")

		// Missing image.
		_, err = r.ResolveTag("zzz", "1.2.3")
		So(err, ShouldErrLike, "no such pinned <image>:<tag> combination in pins YAML")

		// Missing tag.
		_, err = r.ResolveTag("yyy", "blah")
		So(err, ShouldErrLike, "no such pinned <image>:<tag> combination in pins YAML")
	})

	Convey("Incomplete pins", t, func() {
		_, err := ReadPins(strings.NewReader(`{"pins": [
      {"digest": "sha256:123"}
    ]}`))
		So(err, ShouldErrLike, "pin #1: 'image' field is required")

		_, err = ReadPins(strings.NewReader(`{"pins": [
      {"image": "xxx"}
    ]}`))
		So(err, ShouldErrLike, "pin #1: 'digest' field is required")
	})

	Convey("Empty", t, func() {
		r := (&Pins{}).Resolver()
		_, err := r.ResolveTag("img", "tag")
		So(err, ShouldErrLike, "not using pins YAML, the Dockerfile must use @<digest> refs")
	})
}
