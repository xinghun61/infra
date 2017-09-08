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
