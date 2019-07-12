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
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestMaster(t *testing.T) {
	t.Parallel()

	Convey("Master", t, func() {
		c := testContext()
		c = auth.WithState(c, &authtest.FakeState{
			Identity: "user:user@example.com",
		})

		datastore.GetTestable(c).Consistent(true)

		handle := func(c context.Context, master *config.Master) (*masterViewModel, error) {
			model, err := masterPage(c, master)
			if err == nil {
				// assert renders
				_, err := templates.Render(c, "pages/master.html", templates.Args{"Model": model})
				So(err, ShouldBeNil)
			}
			return model, err
		}

		Convey("try server", func() {
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

			master := &config.Master{
				Name:           "tryserver.chromium.linux",
				SchedulingType: config.SchedulingType_TRYJOBS,
			}
			model, err := handle(c, master)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &masterViewModel{
				Master:  master,
				Tryjobs: true,
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

		Convey("waterfall", func() {
			linuxBuilder := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.linux",
					Builder: "Linux Builder",
				},
				Kind: storage.BuilderKind,
			}
			linuxTester := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.linux",
					Builder: "Linux Tester",
				},
				Kind: storage.BuilderKind,
			}

			err := datastore.Put(c, linuxBuilder, linuxTester)
			So(err, ShouldBeNil)

			master := &config.Master{
				Name:           "chromium.linux",
				SchedulingType: config.SchedulingType_CONTINUOUS,
			}
			model, err := handle(c, master)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &masterViewModel{
				Master: master,
				Builders: []masterBuilderViewModel{
					{Builder: linuxBuilder},
					{Builder: linuxTester},
				},
			})
		})

		Convey("ordering", func() {
			deleted := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.foo",
					Builder: "lost from Buildbot",
				},
				Kind:          storage.BuilderKind,
				LUCIIsProd:    false,
				NotOnBuildbot: true,
			}
			needsDecom := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.foo",
					Builder: "needs decom",
				},
				Kind:          storage.BuilderKind,
				LUCIIsProd:    true,
				NotOnBuildbot: false,
			}
			needsFlip := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.foo",
					Builder: "needs flip",
				},
				Kind:          storage.BuilderKind,
				LUCIIsProd:    false,
				NotOnBuildbot: false,
			}
			decommed := &storage.Builder{
				ID: storage.BuilderID{
					Master:  "chromium.foo",
					Builder: "decommed",
				},
				Kind:          storage.BuilderKind,
				LUCIIsProd:    true,
				NotOnBuildbot: true,
			}
			err := datastore.Put(c, deleted, needsDecom, needsFlip, decommed)
			So(err, ShouldBeNil)

			master := &config.Master{
				Name: "chromium.foo",
			}
			model, err := handle(c, master)
			So(err, ShouldBeNil)
			So(model.Builders, ShouldResemble, []masterBuilderViewModel{
				{Builder: needsFlip},
				{Builder: needsDecom},
				{Builder: decommed},
				{Builder: deleted},
			})
		})
	})
}
