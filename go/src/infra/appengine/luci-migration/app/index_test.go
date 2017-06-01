// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package app

import (
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/templates"

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

			c = useConfig(c, `
					buildbot {
						masters {
							name: "tryserver.chromium.linux"
							public: true
						}
						masters {
							name: "tryserver.chromium.mac"
							public: true
						}
						masters {
							name: "tryserver.chromium.win"
							public: true
						}
					}
				`)

			err := datastore.Put(
				c,
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_asan_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
					Public:    true,
				},
				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
					Public:    true,
				},

				&storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.mac",
						Builder: "mac_chromium_rel_ng",
					},
					Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
					Public:    true,
				},
			)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &indexViewModel{
				Masters: []*indexMasterViewModel{
					{
						Name:                   "tryserver.chromium.linux",
						MigratedBuilderCount:   1,
						TotalBuilderCount:      2,
						MigratedBuilderPercent: 50,
					},
					{
						Name:                   "tryserver.chromium.mac",
						MigratedBuilderCount:   1,
						TotalBuilderCount:      1,
						MigratedBuilderPercent: 100,
					},
					{
						Name:                   "tryserver.chromium.win",
						MigratedBuilderCount:   0,
						TotalBuilderCount:      0,
						MigratedBuilderPercent: 0,
					},
				},
			})
		})

		Convey("checks access", func() {
			c = useConfig(c, `
				buildbot {
					masters { name: "tryserver.chromium.linux" }
				}
				`)

			Convey("forbidden", func() {
				c := auth.WithState(c, &authtest.FakeState{
					Identity: "user:user@example.com",
				})

				err := datastore.Put(
					c,
					&storage.Builder{
						ID: storage.BuilderID{
							Master:  "tryserver.chromium.linux",
							Builder: "linux_chromium_rel_ng",
						},
						Migration: storage.BuilderMigration{Status: storage.StatusMigrated},
					},
				)
				So(err, ShouldBeNil)

				model, err := handle(c)
				So(err, ShouldBeNil)
				So(model.Masters, ShouldBeEmpty)
			})

			Convey("allowed", func() {
				c := auth.WithState(c, &authtest.FakeState{
					Identity:       "user:user@example.com",
					IdentityGroups: []string{internalAccessGroup},
				})

				err := datastore.Put(
					c,
					&storage.Builder{
						ID: storage.BuilderID{
							Master:  "tryserver.chromium.linux",
							Builder: "linux_chromium_rel_ng",
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
							MigratedBuilderCount:   1,
							TotalBuilderCount:      1,
							MigratedBuilderPercent: 100,
						},
					},
				})
			})
		})
	})
}
