// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package app

import (
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestIndex(t *testing.T) {
	t.Parallel()

	Convey("Index", t, func() {
		c := testContext()
		datastore.GetTestable(c).Consistent(true)

		handle := func(c context.Context) (*indexViewModel, error) {
			model, err := indexPage(c)
			if err == nil {
				// assert renders
				_, err := templates.Render(c, "pages/index.html", templates.Args{"Model": model})
				So(err, ShouldBeNil)
			}
			return model, err
		}

		Convey("works", func() {
			c := auth.WithState(c, &authtest.FakeState{
				Identity: "user:user@example.com",
			})

			err := datastore.Put(
				c,
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_asan_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
				},
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
				},

				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.mac",
						Builder: "mac_chromium_asan_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusLUCIWAI},
				},
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.mac",
						Builder: "mac_chromium_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
				},
			)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &indexViewModel{
				Masters: []*indexMasterViewModel{
					{
						Name:                   "tryserver.chromium.linux",
						WAIBuilderCount:        1,
						WAIBuilderPercent:      50,
						MigratedBuilderCount:   1,
						MigratedBuilderPercent: 50,
						TotalBuilderCount:      2,
					},
					{
						Name:                   "tryserver.chromium.mac",
						WAIBuilderCount:        2,
						WAIBuilderPercent:      100,
						MigratedBuilderCount:   1,
						MigratedBuilderPercent: 50,
						TotalBuilderCount:      2,
					},
				},
			})
		})
	})
}
