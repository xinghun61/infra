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
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuilder(t *testing.T) {
	t.Parallel()

	Convey("Builder", t, func() {
		c := testContext()
		c = auth.WithState(c, &authtest.FakeState{
			Identity: "user:user@example.com",
		})

		id := storage.BuilderID{
			Master:  "tryserver.chromium.linux",
			Builder: "linux_chromium_rel_ng",
		}

		handle := func(c context.Context) (*builderViewModel, error) {
			model, err := builderPage(c, id)
			if err == nil {
				// assert renders
				_, err := templates.Render(c, "pages/builder.html", templates.Args{"Model": model})
				So(err, ShouldBeNil)
			}
			return model, err
		}

		Convey("builder not found", func() {
			_, err := handle(c)
			So(err, ShouldEqual, errNotFound)
		})

		Convey("status unknown", func() {
			err := datastore.Put(c, &storage.Builder{ID: id})
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model.StatusKnown, ShouldBeFalse)
		})
		Convey("status known, but no BuilderMigrationDetails", func() {
			err := datastore.Put(c, &storage.Builder{
				ID:        id,
				Migration: storage.BuilderMigration{Status: storage.StatusLUCINotWAI},
			})
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model.StatusKnown, ShouldBeFalse)
		})

		Convey("status known", func() {
			builder := &storage.Builder{
				ID: id,
				IssueID: storage.IssueID{
					Hostname: "monorail-prod.appspot.com",
					Project:  "chromium",
					ID:       54,
				},
				Migration: storage.BuilderMigration{
					AnalysisTime: clock.Now(c).UTC().Add(-time.Hour),
					Status:       storage.StatusLUCINotWAI,
					Correctness:  0.9,
					Speed:        1.1,
				},
			}
			migrationDetails := &storage.BuilderMigrationDetails{
				Parent:      datastore.KeyForObj(c, builder),
				TrustedHTML: "almost",
			}
			err := datastore.Put(c, builder, migrationDetails)
			So(err, ShouldBeNil)

			model, err := handle(c)
			So(err, ShouldBeNil)
			So(model, ShouldResemble, &builderViewModel{
				Builder:           builder,
				StatusKnown:       true,
				StatusClassSuffix: "danger",
				StatusAge:         time.Hour,
				Details:           "almost",
				TryBuilder:        false,
			})
		})

		Convey("set experiment percentage", func() {
			builder := &storage.Builder{
				ID:             id,
				SchedulingType: config.SchedulingType_TRYJOBS,
			}
			err := datastore.Put(c, builder)
			So(err, ShouldBeNil)

			rec := httptest.NewRecorder()
			path := "/masters/tryserver.chromium.linux/builders/linux_chromium_rel_ng"
			values := url.Values{}
			values.Set("action", "update")
			values.Set(experimentPercentageFormValueName, "10")
			rc := &router.Context{
				Context: c,
				Params: httprouter.Params{
					httprouter.Param{
						Key:   "master",
						Value: "tryserver.chromium.linux",
					},
					httprouter.Param{
						Key:   "builder",
						Value: "linux_chromium_rel_ng",
					},
				},
				Request: &http.Request{
					URL:  &url.URL{Path: path},
					Form: values,
				},
				Writer: rec,
			}

			Convey("set experiment percentage", func() {
				rc.Context = auth.WithState(rc.Context, &authtest.FakeState{
					Identity:       "user:user@example.com",
					IdentityGroups: []string{changeBuilderSettingsGroup},
				})

				err = handleBuilderPagePost(rc)
				So(err, ShouldBeNil)

				res := rec.Result()
				So(res.StatusCode, ShouldEqual, http.StatusFound)

				err = datastore.Get(c, builder)
				So(err, ShouldBeNil)
				So(builder.ExperimentPercentage, ShouldEqual, 10)
			})
			Convey("set experiment percentage: access denied", func() {
				err = handleBuilderPagePost(rc)
				So(err, ShouldBeNil)
				res := rec.Result()
				So(res.StatusCode, ShouldEqual, http.StatusForbidden)
			})
			Convey("set experiment percentage: not a try builder", func() {
				rc.Context = auth.WithState(rc.Context, &authtest.FakeState{
					Identity:       "user:user@example.com",
					IdentityGroups: []string{changeBuilderSettingsGroup},
				})
				builder := &storage.Builder{ID: id, SchedulingType: config.SchedulingType_CONTINUOUS}
				err := datastore.Put(c, builder)
				So(err, ShouldBeNil)

				err = handleBuilderPagePost(rc)
				So(err, ShouldBeNil)
				res := rec.Result()
				So(res.StatusCode, ShouldEqual, http.StatusBadRequest)
			})
		})
	})
}
