// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"context"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes/duration"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"

	"infra/appengine/arquebus/app/config"
)

func createConfig(id string) *config.Assigner {
	// A sample valid assigner config
	return &config.Assigner{
		Id:        id,
		Owners:    []string{"foo@google.com"},
		Rotations: []string{"oncall1@google.com"},
		Interval:  &duration.Duration{Seconds: 60},
		IssueQuery: &config.IssueQuery{
			Q:            "-has:owner Ops-Alerts=test",
			ProjectNames: []string{"chromium"},
		},
	}
}

func SaveAndGetAll(c context.Context, rev string, cfgs ...*config.Assigner) []*Assigner {
	err := UpdateAssigners(c, cfgs, rev)
	So(err, ShouldBeNil)
	datastore.GetTestable(c).CatchupIndexes()
	aes, err := GetAllAssigners(c)
	So(err, ShouldBeNil)
	return aes
}

func TestUpdateAssigners(t *testing.T) {
	t.Parallel()

	Convey("UpdatedAssigner", t, func() {
		c := memory.Use(context.Background())
		rev1, rev2, rev3 := "abc", "def", "ghi"

		// Ensure empty now.
		datastore.GetTestable(c).CatchupIndexes()
		aes, err := GetAllAssigners(c)
		So(err, ShouldBeNil)
		So(len(aes), ShouldEqual, 0)

		Convey("Creates a new Assigner", func() {
			aes := SaveAndGetAll(c, rev1, createConfig("test-a"))
			So(len(aes), ShouldEqual, 1)
			So(aes[0].ID, ShouldEqual, "test-a")
		})

		Convey("Updates an existing Assigner", func() {
			aes := SaveAndGetAll(c, rev1, createConfig("test-a"))
			So(len(aes), ShouldEqual, 1)
			So(aes[0].ID, ShouldEqual, "test-a")

			// increase the interval just to check the Assigner
			// has been updated or not.
			cfg := createConfig("test-a")
			original := cfg.Interval.Seconds
			cfg.Interval.Seconds = original + 1
			changed := time.Duration(original+1) * time.Second

			Convey("With a new revision", func() {
				aes := SaveAndGetAll(c, rev2, cfg)
				So(len(aes), ShouldEqual, 1)
				So(aes[0].Interval, ShouldEqual, changed)
			})

			Convey("With the same new revision", func() {
				aes := SaveAndGetAll(c, rev1, cfg)
				So(len(aes), ShouldEqual, 1)
				du := time.Duration(original) * time.Second
				So(aes[0].Interval, ShouldEqual, du)
			})
		})

		Convey("Marks as removed if config removed", func() {
			// create
			id := "test-a"
			cfg := createConfig(id)
			aes := SaveAndGetAll(c, rev1, cfg)
			So(len(aes), ShouldEqual, 1)
			So(aes[0].ID, ShouldEqual, id)

			// remove
			aes = SaveAndGetAll(c, rev2)
			So(len(aes), ShouldEqual, 0)

			// put it back
			aes = SaveAndGetAll(c, rev3, cfg)
			So(aes[0].ID, ShouldEqual, id)
		})
	})
}
