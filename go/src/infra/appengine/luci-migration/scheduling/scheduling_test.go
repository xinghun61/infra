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
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	buildbucketpb "go.chromium.org/luci/buildbucket/proto"
	"go.chromium.org/luci/buildbucket/protoutil"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/retry/transient"

	"infra/appengine/luci-migration/config"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestScheduling(t *testing.T) {
	t.Parallel()

	Convey("ParseBuild", t, func() {
		msg := &bbapi.LegacyApiCommonBuildMessage{
			Id:     1,
			Bucket: "luci.chromium.ci",
			Tags: []string{
				"builder:linux",
				"buildset:not a CL",
				"buildset:patch/gerrit/example.com/1/2",
				"luci_migration_attempt:1",
				"luci_migration_buildbot_build_id:54",
			},
			ParametersJson: `{"a": "b"}`,
			CreatedTs:      1514764800000000,
			Status:         bbapi.StatusCompleted,
			Result:         bbapi.ResultSuccess,
			ResultDetailsJson: `{
				"properties": {
					"got_revision": "deadbeef",
					"dry_run": true
				}
			}`,
		}
		build, err := ParseBuild(msg)
		So(err, ShouldBeNil)
		So(build, ShouldResemble, &Build{
			ID:             1,
			Bucket:         "luci.chromium.ci",
			Builder:        "linux",
			ParametersJSON: `{"a": "b"}`,
			CreationTime:   time.Date(2018, 1, 1, 0, 0, 0, 0, time.UTC),
			Change: &buildbucketpb.GerritChange{
				Host:     "example.com",
				Change:   1,
				Patchset: 2,
			},
			Status:      buildbucketpb.Status_SUCCESS,
			GotRevision: "deadbeef",
			DryRun:      true,

			Attempt:         1,
			BuildbotBuildID: 54,
		})
	})

	Convey("Scheduling", t, func(testCtx C) {
		c := context.Background()
		c = memory.Use(c)
		c = config.Use(c, &config.Config{
			Masters: []*config.Master{
				{
					Name:       "tryserver.chromium.linux",
					LuciBucket: "luci.chromium.try",
				},
			},
		})

		change := &buildbucketpb.GerritChange{
			Host:     "gerrit.example.com",
			Change:   1,
			Patchset: 1,
		}

		// Mock buildbucket server.
		putResponseCode := 0
		var actualPutRequests []*bbapi.LegacyApiPutRequestMessage
		var searchResults []*bbapi.LegacyApiCommonBuildMessage
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			var res interface{}
			switch r.URL.Path {
			case "/builds":
				req := &bbapi.LegacyApiPutRequestMessage{}
				err := json.NewDecoder(r.Body).Decode(req)
				testCtx.So(err, ShouldBeNil)
				actualPutRequests = append(actualPutRequests, req)

				if putResponseCode != 0 {
					http.Error(w, "error", putResponseCode)
					return
				}

				res = &bbapi.LegacyApiBuildResponseMessage{
					Build: &bbapi.LegacyApiCommonBuildMessage{Id: 123456789},
				}

			case "/search":
				res = &bbapi.LegacyApiSearchResponseMessage{Builds: searchResults}

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

		h := &Scheduler{
			Buildbucket: bbService,
		}

		Convey("schedules buildbot builds on LUCI", func() {
			Convey("shouldExperiment is deterministic", func() {
				chng := &buildbucketpb.GerritChange{
					Host:     "gerrit.example.com",
					Change:   1,
					Patchset: 1,
				}
				So(shouldExperiment(chng, 50), ShouldBeTrue)
				So(shouldExperiment(chng, 1), ShouldBeFalse)
			})

			c = config.Use(c, &config.Config{
				Masters: []*config.Master{
					{
						Name:       "tryserver.chromium.linux",
						LuciBucket: "luci.chromium.try",
					},
				},
			})

			putBuilder := func(percentage int) {
				err := datastore.Put(c, &storage.Builder{
					ID: storage.BuilderID{
						Master:  "tryserver.chromium.linux",
						Builder: "linux_chromium_rel_ng",
					},
					SchedulingType:       config.SchedulingType_TRYJOBS,
					ExperimentPercentage: percentage,
				})
				So(err, ShouldBeNil)
			}

			b := &Build{
				ID:             54,
				Bucket:         "master.tryserver.chromium.linux",
				Builder:        "linux_chromium_rel_ng",
				Status:         buildbucketpb.Status_SUCCESS,
				Change:         change,
				GotRevision:    "deadbeef",
				ParametersJSON: `{"builder_name": "linux_chromium_rel_ng", "properties":{"revision": "HEAD"}}`,
			}

			Convey("retries buildbot builds on LUCI", func() {
				putBuilder(100)
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldHaveLength, 1)

				var actualParams interface{}
				err = json.Unmarshal([]byte(actualPutRequests[0].ParametersJson), &actualParams)
				So(err, ShouldBeNil)
				So(actualParams, ShouldResemble, map[string]interface{}{
					"builder_name": "linux_chromium_rel_ng",
					"properties": map[string]interface{}{
						"category": "cq_experimental",
						"revision": "deadbeef",
					},
				})

				So(actualPutRequests, ShouldHaveLength, 1)
				So(actualPutRequests, ShouldResemble, []*bbapi.LegacyApiPutRequestMessage{
					{
						Bucket:            "luci.chromium.try",
						ClientOperationId: "luci-migration-retry-54",
						ParametersJson:    actualPutRequests[0].ParametersJson,
						Tags: []string{
							strpair.Format(bbapi.TagBuildSet, protoutil.GerritBuildSet(change)),
							strpair.Format(attemptTagKey, "0"),
							strpair.Format(buildbotBuildIDTagKey, "54"),
							"user_agent:luci-migration",
						},
						Experimental: true,
					},
				})
			})

			Convey("dry_run property is propagated, if set", func() {
				// dry_run may be set by CQ only on presubmit builds.
				b.DryRun = "true"
				putBuilder(100)
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldHaveLength, 1)

				var actualParams interface{}
				err = json.Unmarshal([]byte(actualPutRequests[0].ParametersJson), &actualParams)
				So(err, ShouldBeNil)
				So(actualParams.(map[string]interface{})["properties"], ShouldResemble, map[string]interface{}{
					"category": "cq_experimental",
					"revision": "deadbeef",
					"dry_run":  "true",
				})
			})

			Convey("ignores builders with 0 percentage", func() {
				putBuilder(0)
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldBeEmpty)
			})
		})

		Convey("retries builds", func() {
			Convey("retries LUCI builds", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)

				So(actualPutRequests, ShouldResemble, []*bbapi.LegacyApiPutRequestMessage{
					{
						Bucket:            "luci.test.x",
						ClientOperationId: "luci-migration-retry-54",
						ParametersJson:    b.ParametersJSON,
						Tags: []string{
							strpair.Format(bbapi.TagBuildSet, protoutil.GerritBuildSet(change)),
							strpair.Format(attemptTagKey, "1"),
							strpair.Format(buildbotBuildIDTagKey, "53"),
							"user_agent:luci-migration",
						},
						Experimental: true,
					},
				})
			})

			Convey("retries second time", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Builder:         "some",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldHaveLength, 1) // did retry
				So(strpair.Format(buildbotBuildIDTagKey, "53"), ShouldBeIn, actualPutRequests[0].Tags)
				So(strpair.Format(attemptTagKey, "1"), ShouldBeIn, actualPutRequests[0].Tags)
			})

			Convey("does not retry if there is a newer one", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				searchResults = []*bbapi.LegacyApiCommonBuildMessage{{
					CreatedTs: bbapi.FormatTimestamp(b.CreationTime) + 1, // 1 newer Build
				}}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldBeEmpty)
			})

			Convey("does not retry too many times", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         2,
				}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldBeEmpty) // did not retry
			})

			Convey("does not retry unrecognized builds", func() {
				b := &Build{
					ID:     54,
					Bucket: "luci.chromium.try",
					Status: buildbucketpb.Status_FAILURE,
					// no attempt tag
				}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldBeEmpty) // did not retry
			})

			Convey("does not retry non-failed builds", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.chromium.try",
					Status:          buildbucketpb.Status_SUCCESS,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				err := h.BuildCompleted(c, b)
				So(err, ShouldBeNil)
				So(actualPutRequests, ShouldBeEmpty) // did not retry
			})

			Convey("returns transient error on Buildbucket HTTP 500", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				putResponseCode = 500
				err := h.BuildCompleted(c, b)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeTrue)
			})

			Convey("returns non-transient error on Buildbucket HTTP 403", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				putResponseCode = 403
				err := h.BuildCompleted(c, b)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeFalse)
			})

			Convey("returns non-transient error on Buildbucket HTTP 404", func() {
				b := &Build{
					ID:              54,
					Bucket:          "luci.test.x",
					Status:          buildbucketpb.Status_FAILURE,
					Change:          change,
					BuildbotBuildID: 53,
					Attempt:         0,
				}
				putResponseCode = 404
				err := h.BuildCompleted(c, b)
				So(err, ShouldNotBeNil)
				So(transient.Tag.In(err), ShouldBeFalse)
			})
		})
	})
}
