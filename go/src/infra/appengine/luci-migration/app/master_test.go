// Copyright 2017 The Chromium Authors. All rights reserved.
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

func TestMaster(t *testing.T) {
	t.Parallel()

	Convey("Master", t, func() {
		c := testContext()
		datastore.GetTestable(c).Consistent(true)

		handle := func(c context.Context) (*masterViewModel, error) {
			model, err := masterPage(c, "tryserver.chromium.linux")
			if err == nil {
				// assert renders
				_, err := templates.Render(c, "pages/master.html", templates.Args{"Model": model})
				So(err, ShouldBeNil)
			}
			return model, err
		}

		Convey("master not found", func() {
			_, err := handle(c)
			So(err, ShouldEqual, errNotFound)
		})

		Convey("works", func() {
			c := auth.WithState(c, &authtest.FakeState{
				Identity: "user:user@example.com",
			})

			presubmit := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "chromium_presubmit",
				},
				Kind: storage.BuilderKind,
			}

			asanRelNg := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_asan_rel_ng",
				},
				Kind: storage.BuilderKind,
				Migration: storage.BuilderMigration{
					Status:      storage.StatusLUCINotWAI,
					Correctness: 0.9,
					Speed:       1.1,
				},
			}
			relNg := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "tryserver.chromium.linux",
					Builder: "linux_chromium_rel_ng",
				},
				Kind: storage.BuilderKind,
				Migration: storage.BuilderMigration{
					Status:      storage.StatusMigrated,
					Correctness: 1,
					Speed:       1,
				},
			}
			err := datastore.Put(c, presubmit, asanRelNg, relNg)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &masterViewModel{
				Name: "tryserver.chromium.linux",
				Builders: []masterBuilderViewModel{
					{
						Builder: presubmit,
					},
					{
						Builder:    asanRelNg,
						ShowScores: true,
					},
					{
						Builder:    relNg,
						ShowScores: true,
					},
				},
			})
		})
	})
}
