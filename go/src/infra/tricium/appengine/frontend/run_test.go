// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"html/template"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	ds "go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/tricium/api/v1"
	trit "infra/tricium/appengine/common/testing"
	"infra/tricium/appengine/common/track"
)

func TestRunPageHandler(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &trit.Testing{}
		ctx := tt.Context()

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			next(c)
		}

		r := router.New()
		mw := router.NewMiddlewareChain(withTestingContext)
		mw = mw.Extend(templates.WithTemplates(&templates.Bundle{
			Loader: templates.AssetsLoader(map[string]string{
				"pages/run.html": "{{ .RunInfo | dumpJSON }}",
			}),
			FuncMap: template.FuncMap{
				"dumpJSON": func(v interface{}) (string, error) {
					b, e := json.Marshal(v)
					return string(b), e
				},
			},
		}))
		r.GET("/run/:runId", mw, runPageHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		// Add completed request.
		var runID int64 = 4321
		request := &track.AnalyzeRequest{
			ID: runID,
		}
		So(ds.Put(ctx, request), ShouldBeNil)
		requestKey := ds.KeyForObj(ctx, request)
		So(ds.Put(ctx, &track.AnalyzeRequestResult{
			ID:     1,
			Parent: requestKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		run := &track.WorkflowRun{
			ID:        1,
			Parent:    requestKey,
			Functions: []string{"Hello"},
		}
		So(ds.Put(ctx, run), ShouldBeNil)
		runKey := ds.KeyForObj(ctx, run)
		So(ds.Put(ctx, &track.WorkflowRunResult{
			ID:     1,
			Parent: runKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		platform := tricium.Platform_UBUNTU
		functionKey := ds.NewKey(ctx, "FunctionRun", "Hello", 0, runKey)
		So(ds.Put(ctx, &track.FunctionRun{
			ID:      "Hello",
			Parent:  runKey,
			Workers: []string{"Hello_UBUNTU"},
		}), ShouldBeNil)
		So(ds.Put(ctx, &track.FunctionRunResult{
			ID:     1,
			Parent: functionKey,
			State:  tricium.State_SUCCESS,
		}), ShouldBeNil)
		worker := &track.WorkerRun{
			ID:       "Hello_UBUNTU",
			Parent:   functionKey,
			Platform: platform,
		}
		So(ds.Put(ctx, worker), ShouldBeNil)
		workerKey := ds.KeyForObj(ctx, worker)
		So(ds.Put(ctx, &track.WorkerRunResult{
			ID:          1,
			Parent:      workerKey,
			Function:    "Hello",
			Platform:    tricium.Platform_UBUNTU,
			State:       tricium.State_SUCCESS,
			NumComments: 1,
		}), ShouldBeNil)

		Convey("Successful request", func() {
			resp, err := client.Get(srv.URL + "/run/" + strconv.FormatInt(runID, 10))
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			s := strings.Replace(string(b), "&#34;", "\"", -1) // unescape "
			So(s, ShouldContainSubstring, "Hello_UBUNTU")
		})

		Convey("Invalid run ID", func() {
			w := httptest.NewRecorder()
			routerContext := &router.Context{
				Context: ctx,
				Writer:  w,
				Request: trit.MakeGetRequest(nil),
				Params:  trit.MakeParams("runId", "abc"),
			}
			runPageHandler(routerContext)
			r, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			body := string(r)
			So(w.Code, ShouldEqual, 400)
			So(body, ShouldContainSubstring, "failed to parse run ID")
		})

		Convey("Request not found", func() {
			w := httptest.NewRecorder()
			routerContext := &router.Context{
				Context: ctx,
				Writer:  w,
				Request: trit.MakeGetRequest(nil),
				Params:  trit.MakeParams("runId", "1234"),
			}
			runPageHandler(routerContext)
			r, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			body := string(r)
			So(w.Code, ShouldEqual, 404)
			So(body, ShouldContainSubstring, "failed to get AnalyzeRequest")
		})
	})
}

func TestHelperFunction(t *testing.T) {
	Convey("Test Environment", t, func() {
		Convey("gerritURL with well-formed Gerrit change ref", func() {
			So(gerritURL("https://chromium-review.googlesource.com", "refs/changes/10/12310/3"), ShouldEqual, "https://chromium-review.googlesource.com/c/12310/3")
		})

		// No special effort is made to make a correct URL if the
		// Gerrit revision is badly-formed. Garbage in, garbage out.
		Convey("gerritURL with badly-formed Gerrit change ref", func() {
			So(gerritURL("foo.com", "xxrefs/changes/10/12310/3xx"), ShouldEqual, "foo.com/cxxrefs/changes/10/12310/3xx")
			So(gerritURL("foo.com", "refs/changes/123/4"), ShouldEqual, "foo.com/c/4")
		})
	})
}
