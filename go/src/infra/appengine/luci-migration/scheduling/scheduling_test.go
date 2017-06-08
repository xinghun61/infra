// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package scheduling

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/errors"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestScheduling(t *testing.T) {
	t.Parallel()

	Convey("Scheduling", t, func(testCtx C) {
		c := context.Background()
		c = memory.Use(c)

		// Mock buildbucket server.
		putResponseCode := 0
		var actualPutRequest *buildbucket.ApiPutRequestMessage
		var searchResults []*buildbucket.ApiCommonBuildMessage
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			var res interface{}
			switch r.URL.Path {
			case "/builds":
				actualPutRequest = &buildbucket.ApiPutRequestMessage{}
				err := json.NewDecoder(r.Body).Decode(actualPutRequest)
				testCtx.So(err, ShouldBeNil)

				if putResponseCode != 0 {
					http.Error(w, "error", putResponseCode)
					return
				}

				res = &buildbucket.ApiBuildResponseMessage{
					Build: &buildbucket.ApiCommonBuildMessage{Id: 123456789},
				}

			case "/search":
				res = &buildbucket.ApiSearchResponseMessage{Builds: searchResults}

			default:
				panic("invalid path " + r.URL.Path)
			}

			err := json.NewEncoder(w).Encode(res)
			testCtx.So(err, ShouldBeNil)
		}))
		defer bbServer.Close()
		bbService, err := buildbucket.New(&http.Client{})
		So(err, ShouldBeNil)
		bbService.BasePath = bbServer.URL

		Convey("schedules buildbot builds on LUCI", func() {
			Convey("shouldExperiment is deterministic", func() {
				So(shouldExperiment("foo", 50), ShouldBeTrue)
				So(shouldExperiment("foo", 1), ShouldBeFalse)
			})

			putBuilder := func(percentage int) {
				err := datastore.Put(c, &storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_rel_ng",
					},
					SchedulingType:         config.SchedulingType_TRYJOBS,
					LUCIBuildbucketBucket:  "luci.chromium.try",
					LUCIBuildbucketBuilder: "linux_chromium_rel_ng",
					ExperimentPercentage:   percentage,
				})
				So(err, ShouldBeNil)
			}

			b := &buildbucket.ApiCommonBuildMessage{
				Id:     54,
				Bucket: "master.tryserver.chromium.linux",
				Status: bbutil.StatusCompleted,
				Tags: []string{
					"builder:linux_chromium_rel_ng",
					"buildset:patchsetX",
					"master:tryserver.chromium.linux",
				},
				ParametersJson:    `{"builder_name": "linux_chromium_rel_ng", "properties":{"revision": "HEAD"}}`,
				ResultDetailsJson: `{"properties": {"got_revision": "deadbeef"}}`,
			}

			Convey("retries buildbot builds on LUCI", func() {
				putBuilder(100)
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)

				var actualParams interface{}
				err = json.Unmarshal([]byte(actualPutRequest.ParametersJson), &actualParams)
				So(err, ShouldBeNil)
				So(actualParams, ShouldResemble, map[string]interface{}{
					"builder_name": "linux_chromium_rel_ng",
					"properties": map[string]interface{}{
						"revision": "deadbeef",
					},
				})

				So(actualPutRequest, ShouldResemble, &buildbucket.ApiPutRequestMessage{
					Bucket:            "luci.chromium.try",
					ClientOperationId: "luci-migration-retry-54",
					ParametersJson:    actualPutRequest.ParametersJson,
					Tags: []string{
						bbutil.FormatTag(buildbotBuildIDTagKey, "54"),
						bbutil.FormatTag(attemptTagKey, "0"),
						"buildset:patchsetX",
						"user_agent:luci-migration",
					},
				})

			})
			Convey("ignores builders with 0 percentage", func() {
				putBuilder(0)
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil)
			})
		})

		Convey("retries builds", func() {
			luciMigrationBuildTags := []string{
				bbutil.FormatTag(buildbotBuildIDTagKey, "53"),
				bbutil.FormatTag(attemptTagKey, "0"),
				"buildset:patchsetX",
				"master:masterX",
			}
			Convey("retries LUCI builds", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags:   luciMigrationBuildTags,
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)

				So(actualPutRequest, ShouldResemble, &buildbucket.ApiPutRequestMessage{
					Bucket:            "luci.test.x",
					ClientOperationId: "luci-migration-retry-54",
					ParametersJson:    b.ParametersJson,
					Tags: []string{
						bbutil.FormatTag(buildbotBuildIDTagKey, "53"),
						bbutil.FormatTag(attemptTagKey, "1"),
						"buildset:patchsetX",
						"user_agent:luci-migration",
					},
				})
			})

			Convey("retries second time", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags: []string{
						bbutil.FormatTag(buildbotBuildIDTagKey, "53"),
						bbutil.FormatTag(attemptTagKey, "0"),
						bbutil.FormatTag(bbutil.TagBuildSet, "patch"),
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldNotBeNil) // did retry
				So(bbutil.FormatTag(buildbotBuildIDTagKey, "53"), ShouldBeIn, actualPutRequest.Tags)
				So(bbutil.FormatTag(attemptTagKey, "1"), ShouldBeIn, actualPutRequest.Tags)
			})

			Convey("does not retry if there is a newer one", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags:   luciMigrationBuildTags,
				}
				searchResults = []*buildbucket.ApiCommonBuildMessage{{
					CreatedTs: b.CreatedTs + 1, // 1 newer build
				}}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil)
			})

			Convey("does not retry too many times", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags: []string{
						bbutil.FormatTag(buildbotBuildIDTagKey, "53"),
						bbutil.FormatTag(attemptTagKey, "2"),
						bbutil.FormatTag(bbutil.TagBuildSet, "patch"),
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("does not retry unrecognized builds", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.chromium.try",
					Result: bbutil.ResultFailure,
					// no attempt tag
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("does not retry non-failed builds", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.chromium.try",
					Result: bbutil.ResultSuccess,
					Tags:   luciMigrationBuildTags,
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("returns transient error on Buildbucket HTTP 500", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags:   luciMigrationBuildTags,
				}
				putResponseCode = 500
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(errors.IsTransient(err), ShouldBeTrue)
			})

			Convey("returns non-transient error on Buildbucket HTTP 403", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags:   luciMigrationBuildTags,
				}
				putResponseCode = 403
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(errors.IsTransient(err), ShouldBeFalse)
			})

			Convey("returns non-transient error on Buildbucket HTTP 404", func() {
				b := &buildbucket.ApiCommonBuildMessage{
					Id:     54,
					Bucket: "luci.test.x",
					Result: bbutil.ResultFailure,
					Tags:   luciMigrationBuildTags,
				}
				putResponseCode = 404
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(errors.IsTransient(err), ShouldBeFalse)
			})
		})
	})
}
