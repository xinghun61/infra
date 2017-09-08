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

package analysis

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/appengine/luci-migration/bbutil"
	"infra/appengine/luci-migration/bbutil/buildset"
	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func build(buildset string, duration time.Duration, result string) *buildbucket.ApiCommonBuildMessage {
	return &buildbucket.ApiCommonBuildMessage{
		Tags:        []string{bbutil.FormatTag(bbutil.TagBuildSet, buildset)},
		Status:      bbutil.StatusCompleted,
		Result:      result,
		CreatedTs:   bbutil.FormatTimestamp(testclock.TestRecentTimeUTC),
		StartedTs:   bbutil.FormatTimestamp(testclock.TestRecentTimeUTC),
		CompletedTs: bbutil.FormatTimestamp(testclock.TestRecentTimeUTC.Add(duration)),
	}
}

func TestAnalyze(t *testing.T) {
	t.Parallel()

	Convey("analyze", t, func(testCtx C) {
		c := context.Background()
		c, _ = testclock.UseTime(c, testclock.TestRecentTimeUTC)

		// Mock buildbucket server.
		var luciSearchResults []*buildbucket.ApiCommonBuildMessage
		buildbotSearchResults := map[string][]*buildbucket.ApiCommonBuildMessage{}
		mockBuildbotBuilds := func(setName string, duration time.Duration, results ...string) {
			for _, r := range results {
				buildbotSearchResults[setName] = append(buildbotSearchResults[setName], build(setName, duration, r))
			}
		}
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			res := &buildbucket.ApiSearchResponseMessage{}
			switch r.FormValue("bucket") {
			case "luci.chromium.try":
				res.Builds = luciSearchResults
			case "master.tryserver.chromium.linux":
				buildSet := ""
				for _, t := range r.Form["tag"] {
					if k, v := bbutil.ParseTag(t); k == bbutil.TagBuildSet {
						buildSet = v
						break
					}
				}
				res.Builds = buildbotSearchResults[buildSet]
			}

			err := json.NewEncoder(w).Encode(res)
			testCtx.So(err, ShouldBeNil)
		}))
		defer bbServer.Close()
		bbService, err := buildbucket.New(&http.Client{})
		So(err, ShouldBeNil)
		bbService.BasePath = bbServer.URL

		psAbsent := false
		tryjobs := &Tryjobs{
			Buildbucket: bbService,
			MaxBuildAge: time.Hour * 24 * 7,
			patchSetAbsent: func(context.Context, *http.Client, *buildset.BuildSet) (bool, error) {
				return psAbsent, nil
			},
		}

		buildbotBuilder := BucketBuilder{Bucket: "master.tryserver.chromium.linux", Builder: "linux_chromium_rel_ng"}
		luciBuilder := BucketBuilder{Bucket: "luci.chromium.try", Builder: "linux_chromium_rel_ng"}

		analyze := func() *storage.BuilderMigration {
			mig, html, err := tryjobs.Analyze(
				c,
				buildbotBuilder,
				luciBuilder,
				storage.StatusLUCINotWAI,
			)
			So(err, ShouldBeNil)
			So(html, ShouldNotBeEmpty)
			return mig
		}

		Convey("no luci builds", func() {
			So(analyze(), ShouldResemble, &storage.BuilderMigration{
				AnalysisTime: clock.Now(c),
				Status:       storage.StatusInsufficientData,
			})
		})

		Convey("insufficient common build sets", func() {
			luciSearchResults = []*buildbucket.ApiCommonBuildMessage{
				build("set1", time.Hour, failure),
				build("set1", time.Hour, failure),
				build("set1", time.Hour, failure),
				build("set2", time.Hour, failure),
				build("set2", time.Hour, success),
			}
			mockBuildbotBuilds("set1", time.Hour, failure, failure, failure)
			mockBuildbotBuilds("set3", time.Hour, failure, success)
			tryjobs.MinTrustworthyGroups = 2
			So(analyze().Status, ShouldEqual, storage.StatusInsufficientData)
		})

		Convey("LUCI is correct", func() {
			luciSearchResults = []*buildbucket.ApiCommonBuildMessage{
				build("set1", time.Hour, failure),

				build("set2", time.Hour, failure),
				build("set2", time.Hour, success),

				build("set3", time.Hour, success),
				build("set3", time.Hour, success),
			}
			mockBuildbotBuilds("set1", time.Hour, failure)
			mockBuildbotBuilds("set2", time.Hour, failure, success)
			mockBuildbotBuilds("set3", time.Hour, failure, success)
			mig := analyze()
			So(mig.Status, ShouldEqual, storage.StatusLUCIWAI)
			So(mig.Correctness, ShouldAlmostEqual, 1.0)
		})

		Convey("Ignores Rietveld patchsets that don't exist", func() {
			psAbsent = true

			const buildSetPrefix = "patch/rietveld/rietveld.example.com/1/"

			luciSearchResults = []*buildbucket.ApiCommonBuildMessage{
				build(buildSetPrefix+"1", time.Hour, failure),

				build(buildSetPrefix+"2", time.Hour, failure),
				build(buildSetPrefix+"2", time.Hour, success),

				build(buildSetPrefix+"3", time.Hour, success),
				build(buildSetPrefix+"3", time.Hour, success),
			}
			mockBuildbotBuilds(buildSetPrefix+"1", time.Hour, failure)
			mockBuildbotBuilds(buildSetPrefix+"2", time.Hour, failure, success)
			mockBuildbotBuilds(buildSetPrefix+"3", time.Hour, failure, success)
			mig := analyze()
			So(mig.Status, ShouldEqual, storage.StatusInsufficientData)
		})

		Convey("fetch", func() {
			luciSearchResults = []*buildbucket.ApiCommonBuildMessage{
				build("set1", 10*time.Minute, failure),
				build("set1", 20*time.Minute, failure),
				build("set1", 30*time.Minute, failure),

				build("set2", time.Hour, success),
				build("set2", time.Hour, success),
				build("set2", time.Hour, failure),

				build("set3", time.Hour, success),
			}
			mockBuildbotBuilds("set1", time.Hour, failure, failure, failure)
			mockBuildbotBuilds("set2", time.Hour, failure, success)
			mockBuildbotBuilds("set3", time.Hour, failure, success)

			f := &fetcher{
				Buildbucket: bbService,
				LUCI:        luciBuilder,
				Buildbot:    buildbotBuilder,
				MaxGroups:   DefaultMaxGroups,
				patchSetAbsent: func(context.Context, *http.Client, *buildset.BuildSet) (bool, error) {
					return false, nil
				},
			}
			groups, err := f.Fetch(c)
			So(err, ShouldBeNil)
			So(groups, ShouldHaveLength, 3)
			gmap := map[string]*group{}
			for _, g := range groups {
				gmap[g.Key] = g
			}

			So(gmap["set1"], ShouldNotBeNil)
			So(gmap["set1"].Buildbot, ShouldHaveLength, 3)
			So(gmap["set1"].Buildbot.success(), ShouldBeFalse)
			So(gmap["set1"].LUCI, ShouldHaveLength, 3)
			So(gmap["set1"].LUCI.success(), ShouldBeFalse)
			So(gmap["set1"].LUCI.avgRunDuration(), ShouldEqual, 20*time.Minute)

			So(gmap["set2"], ShouldNotBeNil)
			So(gmap["set2"].Buildbot, ShouldHaveLength, 2)
			So(gmap["set2"].Buildbot.success(), ShouldBeTrue)
			So(gmap["set2"].LUCI, ShouldHaveLength, 3)
			So(gmap["set2"].LUCI.success(), ShouldBeTrue)
			// order must be from oldest to newest
			So(gmap["set2"].LUCI[0].Result, ShouldEqual, failure)
			So(gmap["set2"].LUCI[1].Result, ShouldEqual, success)
			So(gmap["set2"].LUCI[2].Result, ShouldEqual, success)

			So(gmap["set3"], ShouldNotBeNil)
			So(gmap["set3"].Buildbot, ShouldHaveLength, 2)
			So(gmap["set3"].Buildbot.success(), ShouldBeTrue)
			So(gmap["set3"].LUCI, ShouldHaveLength, 1)
			So(gmap["set3"].LUCI.success(), ShouldBeTrue)
		})
	})
}
