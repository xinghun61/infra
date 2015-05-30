// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package meta

import (
	"testing"

	"golang.org/x/net/context"

	"infra/gae/libs/wrapper"
	"infra/gae/libs/wrapper/memory"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetEntityGroupVersion(t *testing.T) {
	t.Parallel()

	Convey("GetEntityGroupVersion", t, func() {
		c := memory.Use(context.Background())
		ds := wrapper.GetDS(c)

		type A struct {
			ID  int64 `datastore:"-" goon:"id"`
			Val int
		}

		a := &A{Val: 10}
		aKey, err := ds.Put(a)
		So(err, ShouldBeNil)

		v, err := GetEntityGroupVersion(c, aKey)
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 1)

		So(ds.Delete(aKey), ShouldBeNil)

		v, err = GetEntityGroupVersion(c, ds.NewKey("madeUp", "thing", 0, aKey))
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 2)

		v, err = GetEntityGroupVersion(c, ds.NewKey("madeUp", "thing", 0, nil))
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 0)

		tDs := ds.(wrapper.Testable)
		tDs.BreakFeatures(nil, "Get")

		v, err = GetEntityGroupVersion(c, aKey)
		So(err.Error(), ShouldContainSubstring, "INTERNAL_ERROR")
	})
}
