// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package storage

import (
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuilderMasterFilter(t *testing.T) {
	t.Parallel()

	Convey("BuilderMasterFilter", t, func() {
		c := context.Background()
		c = memory.Use(c)

		err := datastore.Put(
			c,
			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusMigrated},
			},
			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_asan_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusLUCINotWAI},
			},

			&Builder{
				ID: BuilderID{
					Master:  "tryserver.chromium.mac",
					Builder: "mac_chromium_rel_ng",
				},
				Migration: BuilderMigration{Status: StatusMigrated},
			},
		)
		So(err, ShouldBeNil)
		datastore.GetTestable(c).CatchupIndexes()

		q := datastore.NewQuery(BuilderKind)
		q = BuilderMasterFilter(c, q, "tryserver.chromium.linux")
		var builders []*Builder
		err = datastore.GetAll(c, q, &builders)
		So(err, ShouldBeNil)
		So(builders, ShouldHaveLength, 2)
		So(builders[0].ID.Master, ShouldEqual, "tryserver.chromium.linux")
		So(builders[1].ID.Master, ShouldEqual, "tryserver.chromium.linux")
	})
}
