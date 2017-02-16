// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"infra/appengine/test-results/model"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"

	"time"

	. "github.com/smartystreets/goconvey/convey"
)

func TestCleanTestType(t *testing.T) {
	t.Parallel()

	Convey("cleanTestType", t, func() {
		type testCase struct {
			input, output string
		}
		testCases := []testCase{
			{"base_unittests", "base_unittests"},
			{"base_unittests on Windows XP", "base_unittests"},
			{"base_unittests on Windows XP (with patch)", "base_unittests (with patch)"},
			{"base_unittests on ATI GPU on Windows (with patch) on Windows", "base_unittests (with patch)"},
			{"base_unittests (ATI GPU) on Windows (with patch) on Windows", "base_unittests (with patch)"},
			{"base_unittests on ATI GPU on Windows (without patch) on Windows", "base_unittests"},
			{"Instrumentation test content_shell_test_apk (with patch)", "content_shell_test_apk (with patch)"},
		}
		for _, tc := range testCases {
			So(cleanTestType(tc.input), ShouldEqual, tc.output)
		}
	})
}

func TestBuildersHandler(t *testing.T) {
	t.Parallel()

	Convey("Test loading and serving of builder data.", t, func() {
		ctx := memory.Use(context.Background())

		// Round our test time to microseconds since that's datastore's resolution.
		now := testclock.TestRecentTimeUTC.Round(time.Microsecond)
		ctx, _ = testclock.UseTime(ctx, now)

		tfs := []model.TestFile{
			{
				ID:       1,
				Name:     "results.json",
				Master:   "tryserver.testing",
				Builder:  "testing_chromium_rel_ng",
				TestType: "browser_tests",
				LastMod:  now.AddDate(0, 0, -2),
			},
			{
				ID:       5,
				Name:     "results.json",
				Master:   "tryserver.testing",
				Builder:  "testing_android_rel_ng",
				TestType: "browser_tests",
				LastMod:  now.AddDate(0, 0, -2),
			},
			{
				ID:       2,
				Name:     "results.json",
				Master:   "testing",
				Builder:  "Testing Tests",
				TestType: "browser_tests",
				LastMod:  now,
			},
			{
				ID:       3,
				Name:     "results.json",
				Master:   "testing",
				Builder:  "Stale Testing Tests",
				TestType: "browser_tests",
				LastMod:  now.AddDate(0, 0, -8),
			},
			{
				ID:       4,
				Name:     "results-small.json",
				Master:   "testing",
				Builder:  "Testing Tests",
				TestType: "browser_tests",
				LastMod:  now.UTC(),
			},
		}
		So(datastore.Put(ctx, tfs), ShouldBeNil)

		datastore.GetTestable(ctx).Consistent(true)
		datastore.GetTestable(ctx).AutoIndex(true)
		datastore.GetTestable(ctx).CatchupIndexes()

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			next(c)
		}

		Convey("getRecentTests", func() {
			tests, err := getRecentTests(ctx, 1)
			So(err, ShouldBeNil)
			expected := map[testTriple]struct{}{{
				Master:   "testing",
				Builder:  "Testing Tests",
				TestType: "browser_tests",
			}: struct{}{}}
			So(tests, ShouldResemble, expected)
		})

		Convey("getBuildersHandler", func() {
			r := router.New()
			r.GET("/builders", router.NewMiddlewareChain(withTestingContext),
				getBuildersHandler)
			srv := httptest.NewServer(r)
			client := &http.Client{}

			resp, err := client.Get(srv.URL + "/builders")
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			expected := []model.Master{
				{
					Name:       "testing",
					Identifier: "testing",
					Tests: map[string]*model.Test{
						"browser_tests": {
							Builders: []string{
								"Testing Tests"}}},
				},
				{
					Name:       "tryserver.testing",
					Identifier: "tryserver.testing",
					Tests: map[string]*model.Test{
						"browser_tests": {
							Builders: []string{
								"testing_android_rel_ng",
								"testing_chromium_rel_ng"}}},
				},
			}
			actual := model.BuilderData{}
			So(json.Unmarshal(b, &actual), ShouldBeNil)
			So(actual.NoUploadTestTypes, ShouldResemble, noUploadTestSteps)
			So(actual.Masters, ShouldResemble, expected)
		})
	})
}
