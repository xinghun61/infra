// Copyright 2017 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/auth/identity"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestIndex(t *testing.T) {
	t.Parallel()

	Convey("Index", t, func() {
		c := testContext()
		datastore.GetTestable(c).Consistent(true)

		c = config.Use(c, &config.Config{
			Masters: []*config.Master{
				{
					Name:   "tryserver.chromium.linux",
					Public: true,
				},
				{
					Name:   "tryserver.chromium.mac",
					Public: true,
				},
				{
					Name: "internal.tryserver.chromium.linux",
				},
			},
		})
		c = auth.WithState(c, &authtest.FakeState{Identity: identity.AnonymousIdentity})

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
			err := datastore.Put(
				c,
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_asan_rel_ng",
					},
					LUCIIsProd:    true,
					NotOnBuildbot: false,
					Migration:     storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
				},
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_rel_ng",
					},
					LUCIIsProd:    true,
					NotOnBuildbot: false,
					Migration:     storage.BuilderMigration{Status: storage.StatusMigrated},
				},

				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.mac",
						Builder: "mac_chromium_asan_rel_ng",
					},
					LUCIIsProd:    false,
					NotOnBuildbot: false,
					Migration:     storage.BuilderMigration{Status: storage.StatusLUCIWAI},
				},
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.mac",
						Builder: "mac_chromium_rel_ng",
					},
					LUCIIsProd:    true,
					NotOnBuildbot: true,
					Migration:     storage.BuilderMigration{Status: storage.StatusMigrated},
				},
			)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &indexViewModel{
				Masters: []*indexMasterViewModel{
					{
						Name:                   "tryserver.chromium.linux",
						LUCIBuildbotCounts:     [2][2]int{{0, 0}, {0, 2}},
						WAIBuilderCount:        1,
						WAIBuilderPercent:      50,
						MigratedBuilderCount:   1,
						MigratedBuilderPercent: 50,
						TotalBuilderCount:      2,
					},
					{
						Name:                   "tryserver.chromium.mac",
						LUCIBuildbotCounts:     [2][2]int{{0, 1}, {1, 0}},
						WAIBuilderCount:        2,
						WAIBuilderPercent:      100,
						MigratedBuilderCount:   1,
						MigratedBuilderPercent: 50,
						TotalBuilderCount:      2,
					},
				},
			})
		})
		Convey("internal builder", func() {
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
						Master:  "internal.tryserver.chromium.linux",
						Builder: "linux_chromium_asan_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
				},
			)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &indexViewModel{
				Masters: []*indexMasterViewModel{
					{
						Name:               "tryserver.chromium.linux",
						TotalBuilderCount:  1,
						LUCIBuildbotCounts: [2][2]int{{0, 1}, {0, 0}},
					},
				},
			})
		})
		Convey("has internal access", func() {
			c = auth.WithState(c, &authtest.FakeState{
				Identity:       "user:user@example.com",
				IdentityGroups: []string{accessGroup},
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
						Master:  "internal.tryserver.chromium.linux",
						Builder: "linux_chromium_asan_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
				},
			)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &indexViewModel{
				Masters: []*indexMasterViewModel{
					{
						Name:               "internal.tryserver.chromium.linux",
						TotalBuilderCount:  1,
						LUCIBuildbotCounts: [2][2]int{{0, 1}, {0, 0}},
					},
					{
						Name:               "tryserver.chromium.linux",
						TotalBuilderCount:  1,
						LUCIBuildbotCounts: [2][2]int{{0, 1}, {0, 0}},
					},
				},
			})
		})
	})
}
