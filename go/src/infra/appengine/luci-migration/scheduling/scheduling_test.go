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

package scheduling

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/buildbucket"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/retry/transient"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestScheduling(t *testing.T) {
	t.Parallel()

	Convey("Scheduling", t, func(testCtx C) {
		c := context.Background()
		c = memory.Use(c)

		buildSet := &buildbucket.GerritChange{
			Host:     "gerrit.example.com",
			Change:   1,
			PatchSet: 1,
		}

		// Mock buildbucket server.
		putResponseCode := 0
		var actualPutRequest *bbapi.ApiPutRequestMessage
		var searchResults []*bbapi.ApiCommonBuildMessage
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			var res interface{}
			switch r.URL.Path {
			case "/builds":
				actualPutRequest = &bbapi.ApiPutRequestMessage{}
				err := json.NewDecoder(r.Body).Decode(actualPutRequest)
				testCtx.So(err, ShouldBeNil)

				if putResponseCode != 0 {
					http.Error(w, "error", putResponseCode)
					return
				}

				res = &bbapi.ApiBuildResponseMessage{
					Build: &bbapi.ApiCommonBuildMessage{Id: 123456789},
				}

			case "/search":
				res = &bbapi.ApiSearchResponseMessage{Builds: searchResults}

			default:
				panic("invalid path " + r.URL.Path)
			}

			err := json.NewEncoder(w).Encode(res)
			testCtx.So(err, ShouldBeNil)
		}))
		defer bbServer.Close()
		bbService, err := bbapi.New(&http.Client{})
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
					SchedulingType:        config.SchedulingType_TRYJOBS,
					LUCIBuildbucketBucket: "luci.chromium.try",
					ExperimentPercentage:  percentage,
				})
				So(err, ShouldBeNil)
			}

			b := &Build{
				Build: buildbucket.Build{
					ID:        54,
					Bucket:    "master.tryserver.chromium.linux",
					Builder:   "linux_chromium_rel_ng",
					Status:    buildbucket.StatusSuccess,
					BuildSets: []buildbucket.BuildSet{buildSet},
					Tags: strpair.Map{
						buildbucket.TagBuildSet: []string{buildSet.String()},
						"master":                []string{"tryserver.chromium.linux"},
					},
					Output: buildbucket.Output{
						Properties: &OutputProperties{
							GotRevision: "deadbeef",
						},
					},
				},
				ParametersJSON: `{"builder_name": "linux_chromium_rel_ng", "properties":{"revision": "HEAD"}}`,
			}

			Convey("retries buildbot builds on LUCI", func() {
				putBuilder(100)
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldNotBeNil)

				var actualParams interface{}
				err = json.Unmarshal([]byte(actualPutRequest.ParametersJson), &actualParams)
				So(err, ShouldBeNil)
				So(actualParams, ShouldResemble, map[string]interface{}{
					"builder_name": "linux_chromium_rel_ng",
					"properties": map[string]interface{}{
						"category": "cq_experimental",
						"revision": "deadbeef",
					},
				})

				So(actualPutRequest, ShouldResemble, &bbapi.ApiPutRequestMessage{
					Bucket:            "luci.chromium.try",
					ClientOperationId: "luci-migration-retry-54",
					ParametersJson:    actualPutRequest.ParametersJson,
					Tags: []string{
						strpair.Format(buildbucket.TagBuildSet, buildSet.String()),
						strpair.Format(attemptTagKey, "0"),
						strpair.Format(buildbotBuildIDTagKey, "54"),
						"user_agent:luci-migration",
					},
				})
			})

			Convey("dry_run property is propagated, if set", func() {
				// dry_run may be set by CQ only on presubmit builds.
				b.Build.Output.Properties.(*OutputProperties).DryRun = "true"
				putBuilder(100)
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldNotBeNil)

				var actualParams interface{}
				err = json.Unmarshal([]byte(actualPutRequest.ParametersJson), &actualParams)
				So(err, ShouldBeNil)
				So(actualParams.(map[string]interface{})["properties"], ShouldResemble, map[string]interface{}{
					"category": "cq_experimental",
					"revision": "deadbeef",
					"dry_run":  "true",
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
			luciMigrationBuildTags := strpair.Map{}
			luciMigrationBuildTags.Set(buildbotBuildIDTagKey, "53")
			luciMigrationBuildTags.Set(attemptTagKey, "0")
			luciMigrationBuildTags.Set("buildset", buildSet.String())
			luciMigrationBuildTags.Set("master", "masterX")

			Convey("retries LUCI builds", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.test.x",
						Status: buildbucket.StatusFailure,
						Tags:   luciMigrationBuildTags,
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)

				So(actualPutRequest, ShouldResemble, &bbapi.ApiPutRequestMessage{
					Bucket:            "luci.test.x",
					ClientOperationId: "luci-migration-retry-54",
					ParametersJson:    b.ParametersJSON,
					Tags: []string{
						strpair.Format(buildbucket.TagBuildSet, buildSet.String()),
						strpair.Format(attemptTagKey, "1"),
						strpair.Format(buildbotBuildIDTagKey, "53"),
						"user_agent:luci-migration",
					},
				})
			})

			Convey("retries second time", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:      54,
						Bucket:  "luci.test.x",
						Builder: "some",
						Status:  buildbucket.StatusFailure,
						Tags: strpair.Map{
							buildbotBuildIDTagKey:   []string{"53"},
							attemptTagKey:           []string{"0"},
							buildbucket.TagBuildSet: []string{buildSet.String()},
						},
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldNotBeNil) // did retry
				So(strpair.Format(buildbotBuildIDTagKey, "53"), ShouldBeIn, actualPutRequest.Tags)
				So(strpair.Format(attemptTagKey, "1"), ShouldBeIn, actualPutRequest.Tags)
			})

			Convey("does not retry if there is a newer one", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.test.x",
						Status: buildbucket.StatusFailure,
						Tags:   luciMigrationBuildTags,
					},
				}
				searchResults = []*bbapi.ApiCommonBuildMessage{{
					CreatedTs: buildbucket.FormatTimestamp(b.CreationTime) + 1, // 1 newer Build
				}}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil)
			})

			Convey("does not retry too many times", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:        54,
						Bucket:    "luci.test.x",
						Status:    buildbucket.StatusFailure,
						BuildSets: []buildbucket.BuildSet{buildSet},
						Tags: strpair.Map{
							buildbotBuildIDTagKey: []string{"53"},
							attemptTagKey:         []string{"2"},
						},
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("does not retry unrecognized builds", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.chromium.try",
						Status: buildbucket.StatusFailure,
						// no attempt tag
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("does not retry non-failed builds", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.chromium.try",
						Status: buildbucket.StatusSuccess,
						Tags:   luciMigrationBuildTags,
					},
				}
				err := HandleNotification(c, b, bbService)
				So(err, ShouldBeNil)
				So(actualPutRequest, ShouldBeNil) // did not retry
			})

			Convey("returns transient error on Buildbucket HTTP 500", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.test.x",
						Status: buildbucket.StatusFailure,
						Tags:   luciMigrationBuildTags,
					},
				}
				putResponseCode = 500
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeTrue)
			})

			Convey("returns non-transient error on Buildbucket HTTP 403", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.test.x",
						Status: buildbucket.StatusFailure,
						Tags:   luciMigrationBuildTags,
					},
				}
				putResponseCode = 403
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeFalse)
			})

			Convey("returns non-transient error on Buildbucket HTTP 404", func() {
				b := &Build{
					Build: buildbucket.Build{
						ID:     54,
						Bucket: "luci.test.x",
						Status: buildbucket.StatusFailure,
						Tags:   luciMigrationBuildTags,
					},
				}
				putResponseCode = 404
				err := HandleNotification(c, b, bbService)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeFalse)
			})
		})
	})
}
