// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package app

import (
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/router"
	"github.com/luci/luci-go/server/templates"

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
					Status:      storage.StatusLUCINotWAI,
					Correctness: 0.9,
					Speed:       1.1,
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
				Details:           "almost",
			})
		})

		Convey("set experiment percentage", func() {
			builder := &storage.Builder{ID: id}
			err := datastore.Put(c, builder)
			So(err, ShouldBeNil)

			rec := httptest.NewRecorder()
			path := "/masters/tryserver.chromium.linux/builders/linux_chromium_rel_ng"
			values := url.Values{}
			values.Set(experimentPercentageFormValueName, "10")
			err = handleBuilderPagePost(&router.Context{
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
			})
			So(err, ShouldBeNil)

			res := rec.Result()
			So(res.StatusCode, ShouldEqual, http.StatusFound)

			err = datastore.Get(c, builder)
			So(err, ShouldBeNil)
			So(builder.ExperimentPercentage, ShouldEqual, 10)
		})
	})
}
