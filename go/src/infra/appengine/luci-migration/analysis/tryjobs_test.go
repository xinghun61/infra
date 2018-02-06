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
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	"go.chromium.org/luci/buildbucket"
	bbapi "go.chromium.org/luci/common/api/buildbucket/buildbucket/v1"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/data/strpair"

	"infra/appengine/luci-migration/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func buildMsg(key groupKey, duration time.Duration, result string) *bbapi.ApiCommonBuildMessage {
	return &bbapi.ApiCommonBuildMessage{
		Tags:              []string{strpair.Format(buildbucket.TagBuildSet, key.GerritChange.String())},
		Status:            "COMPLETED",
		Result:            result,
		CreatedBy:         "user:someone@example.com",
		CreatedTs:         buildbucket.FormatTimestamp(testclock.TestRecentTimeUTC),
		StartedTs:         buildbucket.FormatTimestamp(testclock.TestRecentTimeUTC),
		CompletedTs:       buildbucket.FormatTimestamp(testclock.TestRecentTimeUTC.Add(duration)),
		ResultDetailsJson: fmt.Sprintf(`{"properties": {"got_revision": %q}}`, key.GotRevision),
	}
}

type mockedBuilds struct {
	successes int
	failures  int
}
type mockedBuildSet struct {
	Buildbot mockedBuilds
	LUCI     mockedBuilds
}

func TestAnalyze(t *testing.T) {
	t.Parallel()

	Convey("analyze", t, func(testCtx C) {
		c := context.Background()
		c, _ = testclock.UseTime(c, testclock.TestRecentTimeUTC)

		// Mock buildbucket server.
		var buildSets []mockedBuildSet
		bbServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			res := &bbapi.ApiSearchResponseMessage{}
			defer func() {
				err := json.NewEncoder(w).Encode(res)
				testCtx.So(err, ShouldBeNil)
			}()

			tags := strpair.ParseMap(r.URL.Query()["tag"])
			buildSet := tags.Get(buildbucket.TagBuildSet)
			if buildSet == "" {
				for i := 0; i < len(buildSets); i++ {
					// only group key matters here, the rest is ignored
					patchSet := i + 1
					res.Builds = append(res.Builds, buildMsg(mkKey(patchSet), time.Hour, bbapi.ResultSuccess))
				}
				return
			}

			cl, ok := buildbucket.ParseBuildSet(buildSet).(*buildbucket.GerritChange)
			testCtx.So(ok, ShouldBeTrue)
			testCtx.So(cl.PatchSet, ShouldBeBetween, 0, len(buildSets)+1)
			key := mkKey(cl.PatchSet)
			testCtx.So(cl, ShouldResemble, &key.GerritChange)

			var spec mockedBuilds
			switch r.FormValue("bucket") {
			case "luci.chromium.try":
				spec = buildSets[cl.PatchSet-1].LUCI
			case "master.tryserver.chromium.linux":
				spec = buildSets[cl.PatchSet-1].Buildbot
			}

			// the order of res.Builds is newest to oldest.
			for i := 0; i < spec.successes; i++ {
				res.Builds = append(res.Builds, buildMsg(key, time.Hour, bbapi.ResultSuccess))
			}
			for i := 0; i < spec.failures; i++ {
				res.Builds = append(res.Builds, buildMsg(key, time.Hour, bbapi.ResultFailure))
			}
		}))
		defer bbServer.Close()
		bbService, err := bbapi.New(&http.Client{})
		So(err, ShouldBeNil)
		bbService.BasePath = bbServer.URL

		tryjobs := &Tryjobs{
			Buildbucket: bbService,
			MaxBuildAge: time.Hour * 24 * 7,
		}

		analyze := func() *storage.BuilderMigration {
			mig, html, err := tryjobs.Analyze(
				c,
				"linux_chromium_rel_ng",
				"master.tryserver.chromium.linux",
				"luci.chromium.try",
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
			buildSets = []mockedBuildSet{
				{
					Buildbot: mockedBuilds{failures: 3},
					LUCI:     mockedBuilds{failures: 3},
				},
				{
					LUCI: mockedBuilds{failures: 1, successes: 1},
				},
				{
					Buildbot: mockedBuilds{failures: 1, successes: 1},
				},
			}
			tryjobs.MinTrustworthyGroups = 2
			So(analyze().Status, ShouldEqual, storage.StatusInsufficientData)
		})

		Convey("LUCI is correct", func() {
			buildSets = []mockedBuildSet{
				{
					Buildbot: mockedBuilds{failures: 1},
					LUCI:     mockedBuilds{failures: 1},
				},
				{
					Buildbot: mockedBuilds{failures: 1},
					LUCI:     mockedBuilds{failures: 1},
				},
				{
					Buildbot: mockedBuilds{failures: 0, successes: 2},
					LUCI:     mockedBuilds{failures: 1, successes: 1},
				},
			}
			mig := analyze()
			So(mig.Status, ShouldEqual, storage.StatusLUCIWAI)
			So(mig.Correctness, ShouldAlmostEqual, 1.0)
			So(mig.InfraHealth, ShouldAlmostEqual, 1.0)
		})

		Convey("fetch", func() {
			buildSets = []mockedBuildSet{
				{
					Buildbot: mockedBuilds{failures: 3},
					LUCI:     mockedBuilds{failures: 3},
				},
				{
					Buildbot: mockedBuilds{failures: 1, successes: 1},
					LUCI:     mockedBuilds{failures: 1, successes: 2},
				},
				{
					Buildbot: mockedBuilds{failures: 1, successes: 1},
					LUCI:     mockedBuilds{successes: 1},
				},
			}
			f := &fetcher{
				Buildbucket:    bbService,
				Builder:        "linux_chromium_rel_ng",
				BuildbotBucket: "master.tryserver.chromium.linux",
				LUCIBucket:     "luci.chromium.try",
				MaxGroups:      DefaultMaxGroups,
			}
			groups, err := f.Fetch(c)
			So(err, ShouldBeNil)
			So(groups, ShouldHaveLength, 3)
			gmap := map[groupKey]*group{}
			for _, g := range groups {
				gmap[g.Key] = g
			}

			set0 := gmap[mkKey(1)]
			So(set0, ShouldNotBeNil)
			So(set0.Buildbot, ShouldHaveLength, 3)
			So(set0.Buildbot.success(), ShouldBeFalse)
			So(set0.LUCI, ShouldHaveLength, 3)
			So(set0.LUCI.success(), ShouldBeFalse)

			set1 := gmap[mkKey(2)]
			So(set1, ShouldNotBeNil)
			So(set1.Buildbot, ShouldHaveLength, 2)
			So(set1.Buildbot.success(), ShouldBeTrue)
			So(set1.LUCI, ShouldHaveLength, 3)
			So(set1.LUCI.success(), ShouldBeTrue)
			// order must be from oldest to newest
			So(set1.LUCI[0].Status, ShouldEqual, buildbucket.StatusFailure)
			So(set1.LUCI[1].Status, ShouldEqual, buildbucket.StatusSuccess)
			So(set1.LUCI[2].Status, ShouldEqual, buildbucket.StatusSuccess)

			set2 := gmap[mkKey(3)]
			So(set2, ShouldNotBeNil)
			So(set2.Buildbot, ShouldHaveLength, 2)
			So(set2.Buildbot.success(), ShouldBeTrue)
			So(set2.LUCI, ShouldHaveLength, 1)
			So(set2.LUCI.success(), ShouldBeTrue)
		})
	})
}

func mkKey(patchSet int) groupKey {
	return groupKey{
		GerritChange: buildbucket.GerritChange{
			Host:     "gerrit.example.com",
			Change:   1,
			PatchSet: patchSet,
		},
		GotRevision: "deadbeef",
	}
}
