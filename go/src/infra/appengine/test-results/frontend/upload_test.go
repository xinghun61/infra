// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"encoding/json"
	"infra/appengine/test-results/model"
	"io"
	"io/ioutil"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"
	. "github.com/smartystreets/goconvey/convey"
)

func TestUploadAndGetHandlers(t *testing.T) {
	t.Parallel()

	ctx := memory.Use(context.Background())
	testFileIdx, err := datastore.FindAndParseIndexYAML(filepath.Join("testdata"))
	if err != nil {
		panic(err)
	}
	ds := datastore.Get(ctx)
	ds.Testable().AddIndexes(testFileIdx...)

	withTestingContext := func(c *router.Context, next router.Handler) {
		c.Context = ctx
		ds.Testable().CatchupIndexes()
		next(c)
	}

	r := router.New()
	mw := router.NewMiddlewareChain(withTestingContext)
	r.GET("/testfile", mw.Extend(templatesMiddleware()), getHandler)
	r.POST("/testfile/upload", mw.Extend(withParsedUploadForm), uploadHandler)
	srv := httptest.NewServer(r)
	client := &http.Client{}

	Convey("Upload and Get handlers", t, func() {
		Convey("upload full_results.json", func() {
			var buf bytes.Buffer
			multi := multipart.NewWriter(&buf)
			// Form files.
			f, err := os.Open(filepath.Join("testdata", "full_results_0.json"))
			So(err, ShouldBeNil)
			defer f.Close()
			multiFile, err := multi.CreateFormFile("file", "full_results.json")
			So(err, ShouldBeNil)
			_, err = io.Copy(multiFile, f)
			So(err, ShouldBeNil)
			// Form fields.
			fields := []struct {
				key, val string
			}{
				{"master", "chromium.chromiumos"},
				{"builder", "test-builder"},
				{"testtype", "test-type"},
			}
			for _, field := range fields {
				f, err := multi.CreateFormField(field.key)
				So(err, ShouldBeNil)
				_, err = f.Write([]byte(field.val))
				So(err, ShouldBeNil)
			}
			multi.Close()

			req, err := http.NewRequest("POST", srv.URL+"/testfile/upload", &buf)
			So(err, ShouldBeNil)
			req.Header.Set("Content-Type", multi.FormDataContentType())
			resp, err := client.Do(req)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusOK)

			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "OK")

			// Get results.json for uploaded full_results.json
			req, err = http.NewRequest("GET", srv.URL+"/testfile?"+url.Values{
				"master":   {"chromium.chromiumos"},
				"builder":  {"test-builder"},
				"testtype": {"test-type"},
				"name":     {"results.json"},
			}.Encode(), nil)
			So(err, ShouldBeNil)
			resp, err = client.Do(req)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusOK)

			var aggr model.AggregateResult
			So(json.NewDecoder(resp.Body).Decode(&aggr), ShouldBeNil)
			So(aggr, ShouldResemble, model.AggregateResult{
				Version: model.ResultsVersion,
				Builder: "test-builder",
				BuilderInfo: &model.BuilderInfo{
					SecondsEpoch: []int64{1406123456},
					BuildNumbers: []model.Number{123},
					ChromeRevs:   []string{"67890"},
					Tests: model.AggregateTest{
						"Test1.testproc1": &model.AggregateTestLeaf{
							Results:  []model.ResultSummary{{1, "Q"}},
							Runtimes: []model.RuntimeSummary{{1, 1}},
						},
					},
					FailuresByType: map[string][]int{
						"FAIL": {0},
						"PASS": {1},
						"SKIP": {0},
					},
					FailureMap: model.FailureLongNames,
				},
			})

			// Get test list JSON for uploaded full_results.json
			req, err = http.NewRequest("GET", srv.URL+"/testfile?"+url.Values{
				"master":       {"chromium.chromiumos"},
				"builder":      {"test-builder"},
				"testtype":     {"test-type"},
				"name":         {"results.json"},
				"testlistjson": {"1"},
			}.Encode(), nil)
			So(err, ShouldBeNil)
			resp, err = client.Do(req)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusOK)

			b, err = ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(resp.Header.Get("Content-Type"), ShouldContainSubstring, "application/json")
			So(bytes.TrimSpace(b), ShouldResemble, []byte(`{"test-builder":{"tests":{"Test1.testproc1":{}}}}`))

			// HTML response
			req, err = http.NewRequest("GET", srv.URL+"/testfile?"+url.Values{
				"master":   {"chromium.chromiumos"},
				"builder":  {"test-builder"},
				"testtype": {"test-type"},
				"name":     {"full_results.json"},
			}.Encode(), nil)
			So(err, ShouldBeNil)
			resp, err = client.Do(req)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusOK)
			So(resp.Header.Get("Content-Type"), ShouldContainSubstring, "text/html")
		})
	})
}

func TestUploadTestFile(t *testing.T) {
	t.Parallel()

	Convey("uploadTestFile", t, func() {
		Convey("data too large to fit in single datastore blob", func() {
			ctx := memory.Use(context.Background())
			ctx = SetUploadParams(ctx, &UploadParams{
				Master:   "foo",
				Builder:  "bar",
				TestType: "baz",
			})
			data, err := ioutil.ReadFile(filepath.Join("testdata", "full_results_0.json"))
			So(err, ShouldBeNil)
			data = bytes.TrimSpace(data)
			So(uploadTestFile(ctx, bytes.NewReader(data), "full_results.json"), ShouldBeNil)

			Convey("get uploaded data", func() {
				datastore.Get(ctx).Testable().CatchupIndexes()
				q := datastore.NewQuery("TestFile")
				q = q.Eq("master", "foo")
				q = q.Eq("builder", "bar")
				q = q.Eq("test_type", "baz")
				q = q.Eq("name", "full_results.json")
				tf, err := getFirstTestFile(ctx, q)
				So(err, ShouldBeNil)

				reader, err := tf.DataReader(ctx)
				So(err, ShouldBeNil)
				b, err := ioutil.ReadAll(reader)
				So(err, ShouldBeNil)
				So(bytes.TrimSpace(b), ShouldResemble, data)
			})
		})
	})
}

func TestUpdateIncremental(t *testing.T) {
	t.Parallel()

	Convey("updateIncremental", t, func() {
		Convey("simple: updates corresponding aggregate files", func() {
			ctx := memory.Use(context.Background())
			idx, err := datastore.FindAndParseIndexYAML(filepath.Join("testdata"))
			So(err, ShouldBeNil)
			ds := datastore.Get(ctx)
			ds.Testable().AddIndexes(idx...)
			ds.Testable().CatchupIndexes()

			data, err := ioutil.ReadFile(filepath.Join("testdata", "results_0.json"))
			So(err, ShouldBeNil)
			var orig model.AggregateResult
			So(json.Unmarshal(data, &orig), ShouldBeNil)
			resultsTf := model.TestFile{
				Name:        "results.json",
				Master:      "chromium.swarm",
				TestType:    "content_unittests",
				Builder:     "Linux Swarm",
				BuildNumber: -1,
			}
			So(resultsTf.PutData(ctx, func(w io.Writer) error {
				_, err := w.Write(data)
				return err
			}), ShouldBeNil)
			So(ds.Put(&resultsTf), ShouldBeNil)
			ds.Testable().CatchupIndexes()

			incr := model.AggregateResult{
				Builder: "Linux Swarm",
				BuilderInfo: &model.BuilderInfo{
					BuildNumbers: []model.Number{7399},
				},
			}
			So(updateIncremental(SetUploadParams(ctx, &UploadParams{
				Master:   "chromium.swarm",
				TestType: "content_unittests",
				Builder:  "Linux Swarm",
			}), &incr), ShouldBeNil)

			Convey("updates without error", func() {
				ds.Testable().CatchupIndexes()
				q := datastore.NewQuery("TestFile")
				q = q.Eq("master", "chromium.swarm")
				q = q.Eq("test_type", "content_unittests")
				q = q.Eq("builder", "Linux Swarm")
				q = q.Eq("name", "results.json")
				tf, err := getFirstTestFile(ctx, q)
				So(err, ShouldBeNil)

				reader, err := tf.DataReader(ctx)
				So(err, ShouldBeNil)
				var updated model.AggregateResult
				So(json.NewDecoder(reader).Decode(&updated), ShouldBeNil)

				// TODO(nishanths): also check `updated` ShouldResemble `expected`.
			})
		})
	})
}
