// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package meta

import (
	"testing"

	"golang.org/x/net/context"

	"infra/gae/libs/gae"
	"infra/gae/libs/gae/memory"

	. "github.com/smartystreets/goconvey/convey"
)

func TestGetEntityGroupVersion(t *testing.T) {
	t.Parallel()

	Convey("GetEntityGroupVersion", t, func() {
		c := memory.Use(context.Background())
		rds := gae.GetRDS(c)

		aKey, err := rds.Put(rds.NewKey("A", "", 0, nil), gae.DSPropertyMap{
			"Val": {gae.MkDSProperty(10)},
		})
		So(err, ShouldBeNil)

		v, err := GetEntityGroupVersion(c, aKey)
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 1)

		So(rds.Delete(aKey), ShouldBeNil)

		v, err = GetEntityGroupVersion(c, rds.NewKey("madeUp", "thing", 0, aKey))
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 2)

		v, err = GetEntityGroupVersion(c, rds.NewKey("madeUp", "thing", 0, nil))
		So(err, ShouldBeNil)
		So(v, ShouldEqual, 0)

		tDs := rds.(gae.Testable)
		tDs.BreakFeatures(nil, "Get")

		v, err = GetEntityGroupVersion(c, aKey)
		So(err.Error(), ShouldContainSubstring, "INTERNAL_ERROR")
	})
}
