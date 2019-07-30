// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"bytes"
	"errors"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestPins(t *testing.T) {
	t.Parallel()

	pinsYAML := `{"pins": [
		{"image": "library/yyy", "tag": "old", "digest": "sha256:456"},
		{"image": "xxx", "digest": "sha256:123", "comment": "zzz", "freeze": "yyy"},
		{"image": "gcr.io/example/zzz", "tag": "1.2.3", "digest": "sha256:789"}
	]}`

	Convey("Works", t, func() {
		p, err := ReadPins(strings.NewReader(pinsYAML))
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

	Convey("Duplicate pins YAML", t, func() {
		_, err := ReadPins(strings.NewReader(`{"pins": [
			{"image": "library/xxx", "tag": "tag", "digest": "sha256:456"},
			{"image": "library/xxx", "tag": "another", "digest": "sha256:456"},  # OK
			{"image": "xxx", "tag": "tag", "digest": "sha256:456"}               # dup
		]}`))
		So(err, ShouldErrLike, `pin #3: duplicate entry for "docker.io/library/xxx:tag"`)
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

	Convey("WritePins", t, func() {
		p, err := ReadPins(strings.NewReader(pinsYAML))
		So(err, ShouldBeNil)

		out := bytes.Buffer{}
		So(WritePins(&out, p), ShouldBeNil)
		So(out.String(), ShouldEqual, `# Managed by cloudbuildhelper.
#
# All comments or unrecognized fields will be overwritten. To comment an entry
# use "comment" field.
#
# To update digests of all entries:
#   $ cloudbuildhelper pins-update <path-to-this-file>
#
# To add an entry (or update an existing one):
#   $ cloudbuildhelper pins-add <path-to-this-file> <image>[:<tag>]
#
# To remove an entry just delete it from the file.
#
# To prevent an entry from being updated by pins-update, add "freeze" field with
# an explanation why it is frozen.

pins:
- comment: zzz
  image: docker.io/library/xxx
  tag: latest
  digest: sha256:123
  freeze: yyy
- image: docker.io/library/yyy
  tag: old
  digest: sha256:456
- image: gcr.io/example/zzz
  tag: 1.2.3
  digest: sha256:789
`)
	})

	Convey("Add", t, func() {
		p := Pins{}

		// Adds new, normalizing it.
		So(p.Add(Pin{Image: "xxx", Digest: "yyy"}), ShouldBeNil)
		So(p.Pins, ShouldResemble, []Pin{
			{Image: "docker.io/library/xxx", Tag: "latest", Digest: "yyy"},
		})

		// Overwrites existing.
		So(p.Add(Pin{Image: "library/xxx", Digest: "zzz"}), ShouldBeNil)
		So(p.Pins, ShouldResemble, []Pin{
			{Image: "docker.io/library/xxx", Tag: "latest", Digest: "zzz"},
		})

		// Handle bad pins.
		So(p.Add(Pin{}), ShouldErrLike, `'image' field is required`)
	})

	Convey("Visit success", t, func() {
		p := Pins{Pins: []Pin{
			{Image: "example.com/repo/img1", Tag: "t1", Digest: "d1"},
			{Image: "example.com/repo/img1", Tag: "t2", Digest: "d2"},
			{Image: "example.com/repo/img2", Tag: "t3", Digest: "d3"},
			{Image: "example.com/repo/img2", Tag: "t4", Digest: "d4"},
		}}

		err := p.Visit(func(p *Pin) error {
			p.Digest += "_new"
			return nil
		})
		So(err, ShouldBeNil)

		So(p.Pins, ShouldResemble, []Pin{
			{Image: "example.com/repo/img1", Tag: "t1", Digest: "d1_new"},
			{Image: "example.com/repo/img1", Tag: "t2", Digest: "d2_new"},
			{Image: "example.com/repo/img2", Tag: "t3", Digest: "d3_new"},
			{Image: "example.com/repo/img2", Tag: "t4", Digest: "d4_new"},
		})
	})

	Convey("Visit failure", t, func() {
		p := Pins{Pins: []Pin{
			{Image: "example.com/repo/img1", Tag: "t1", Digest: "d1"},
			{Image: "example.com/repo/img1", Tag: "t2", Digest: "d2"},
			{Image: "example.com/repo/img2", Tag: "t3", Digest: "d3"},
			{Image: "example.com/repo/img2", Tag: "t4", Digest: "d4"},
		}}

		err := p.Visit(func(p *Pin) error {
			p.Digest += "_new"
			if p.Image == "example.com/repo/img2" {
				return errors.New("blarg")
			}
			return nil
		})
		So(err, ShouldErrLike, `blarg (and 1 other error)`)

		// Updated only img1 ones.
		So(p.Pins, ShouldResemble, []Pin{
			{Image: "example.com/repo/img1", Tag: "t1", Digest: "d1_new"},
			{Image: "example.com/repo/img1", Tag: "t2", Digest: "d2_new"},
			{Image: "example.com/repo/img2", Tag: "t3", Digest: "d3"},
			{Image: "example.com/repo/img2", Tag: "t4", Digest: "d4"},
		})
	})
}
