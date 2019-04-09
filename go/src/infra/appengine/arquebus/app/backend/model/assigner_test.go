// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"context"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
)

func TestUpdateAssigners(t *testing.T) {
	t.Parallel()

	Convey("UpdateAssigners", t, func() {
		c := memory.Use(context.Background())
		rev1, rev2, rev3 := "abc", "def", "ghi"

		// Ensure empty now.
		datastore.GetTestable(c).CatchupIndexes()
		assigners, err := GetAllAssigners(c)
		So(err, ShouldBeNil)
		So(len(assigners), ShouldEqual, 0)

		Convey("Creates a new Assigner", func() {
			assigners := updateAndGetAllAssigners(
				c, rev1, createConfig("test-a"))
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, "test-a")
		})

		Convey("Updates an existing Assigner", func() {
			assigners := updateAndGetAllAssigners(c, rev1, createConfig("test-a"))
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, "test-a")

			// increase the interval just to check the Assigner
			// has been updated or not.
			cfg := createConfig("test-a")
			original := cfg.Interval.Seconds
			cfg.Interval.Seconds = original + 1
			changed := time.Duration(original+1) * time.Second

			Convey("With a new revision", func() {
				assigners := updateAndGetAllAssigners(c, rev2, cfg)
				So(len(assigners), ShouldEqual, 1)
				So(assigners[0].Interval, ShouldEqual, changed)
			})

			Convey("With the same new revision", func() {
				assigners := updateAndGetAllAssigners(c, rev1, cfg)
				So(len(assigners), ShouldEqual, 1)
				du := time.Duration(original) * time.Second
				So(assigners[0].Interval, ShouldEqual, du)
			})
		})

		Convey("Marks as removed if config removed", func() {
			// create
			id := "test-a"
			cfg := createConfig(id)
			assigners := updateAndGetAllAssigners(c, rev1, cfg)
			So(len(assigners), ShouldEqual, 1)
			So(assigners[0].ID, ShouldEqual, id)

			// remove
			assigners = updateAndGetAllAssigners(c, rev2)
			So(len(assigners), ShouldEqual, 0)

			// put it back
			assigners = updateAndGetAllAssigners(c, rev3, cfg)
			So(assigners[0].ID, ShouldEqual, id)
		})
	})
}
