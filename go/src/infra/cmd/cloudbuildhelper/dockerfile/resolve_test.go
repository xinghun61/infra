// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"fmt"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestResolve(t *testing.T) {
	t.Parallel()

	res := mapResolver{
		"img1:tag1":   "res1",
		"img2:latest": "lat",
	}

	call := func(in string) string {
		out, err := Resolve([]byte(in), res)
		So(err, ShouldBeNil)
		return string(out)
	}

	callErr := func(in string) error {
		_, err := Resolve([]byte(in), res)
		return err
	}

	Convey("Pass through", t, func() {
		same := func(in string) bool { return call(in) == in }

		So(same(``), ShouldBeTrue)
		So(same(`# Comment

And stuff

`), ShouldBeTrue)
		So(same(`
DIRECTIVE 1
FROMM 1
`), ShouldBeTrue)
	})

	Convey("Resolves stuff", t, func() {
		So(call(`FROM img1:tag1`), ShouldEqual, `FROM img1@res1`)
		So(call(`FROM img1:tag1   AS Blarg #  Zzz  zz`), ShouldEqual, `FROM img1@res1 AS Blarg # Zzz zz`)

		So(call(`
  FROM img1:tag1
  FROM imgZ@sha256:already_digest
  FROM scratch:wat
  FROM img2`), ShouldEqual, `
FROM img1@res1
FROM imgZ@sha256:already_digest
FROM scratch
FROM img2@lat`)
	})

	Convey("Errors", t, func() {
		So(callErr(`from`), ShouldErrLike, `line 1: expecting 'FROM <image>', got only FROM`)
		So(callErr(`from # blah`), ShouldErrLike, `line 1: resolving "#:latest": no such tag`)
		So(callErr(`FROM base:${CODE_VERSION}`), ShouldErrLike, `line 1: bad FROM reference "base:${CODE_VERSION}", ARGs in FROM are not supported by cloudbuildhelper`)
	})
}

// mapResolver implements Resolver via map.
type mapResolver map[string]string

func (m mapResolver) ResolveTag(image, tag string) (digest string, err error) {
	d, ok := m[fmt.Sprintf("%s:%s", image, tag)]
	if !ok {
		return "", fmt.Errorf("no such tag")
	}
	return d, nil
}
