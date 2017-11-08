// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"infra/appengine/test-results/model"
	"io"
	"io/ioutil"
	"mime/multipart"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

type AlwaysInWhitelistAuthDB struct {
	authtest.FakeDB
}

func (db AlwaysInWhitelistAuthDB) IsInWhitelist(c context.Context, ip net.IP, whitelist string) (bool, error) {
	return true, nil
}

func createTestUploadRequest(serverURL string, master string, data []byte) *http.Request {
	var buf bytes.Buffer
	multi := multipart.NewWriter(&buf)
	multiFile, err := multi.CreateFormFile("file", "full_results.json")
	So(err, ShouldBeNil)
	_, err = io.Copy(multiFile, bytes.NewReader(data))
	So(err, ShouldBeNil)

	// Form fieldatastore.
	fields := []struct {
		key, val string
	}{
		{"master", master},
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

	req, err := http.NewRequest("POST", serverURL+"/testfile/upload", &buf)
	So(err, ShouldBeNil)
	req.Header.Set("Content-Type", multi.FormDataContentType())
	return req
}

func TestUploadAndGetHandlers(t *testing.T) {
	t.Parallel()

	ctx := memory.Use(context.Background())
	testFileIdx, err := datastore.FindAndParseIndexYAML(filepath.Join("testdata"))
	if err != nil {
		panic(err)
	}
	datastore.GetTestable(ctx).AddIndexes(testFileIdx...)

	withTestingContext := func(c *router.Context, next router.Handler) {
		c.Context = auth.WithState(ctx, &authtest.FakeState{
			PeerIPOverride: net.IP{1, 2, 3, 4},
			FakeDB:         AlwaysInWhitelistAuthDB{},
		})
		datastore.GetTestable(ctx).CatchupIndexes()
		next(c)
	}

	r := router.New()
	mw := router.NewMiddlewareChain(withTestingContext)
	r.GET("/testfile", mw.Extend(templatesMiddleware()), getHandler)
	r.POST("/testfile/upload", mw.Extend(withParsedUploadForm), uploadHandler)
	srv := httptest.NewTLSServer(r)

	// Create a client that ignores bad certificates. This is needed to generate
	// mock HTTPS requests below.
	client := &http.Client{
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		},
	}

	Convey("Upload and Get handlers", t, func() {
		// Read test file data.
		frFile, err := os.Open(filepath.Join("testdata", "full_results_0.json"))
		So(err, ShouldBeNil)
		defer frFile.Close()
		frData, err := ioutil.ReadAll(frFile)
		So(err, ShouldBeNil)

		Convey("upload full_results.json", func() {
			Convey("with whitelisted master", func() {
				req := createTestUploadRequest(srv.URL, "chromium.chromiumos", frData)
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
						SecondsEpoch: []float64{1406123456},
						BuildNumbers: []model.Number{123},
						ChromeRevs:   []string{"67890"},
						Tests: model.AggregateTest{
							"Test1.testproc1": &model.AggregateTestLeaf{
								Results:  []model.ResultSummary{{Count: 1, Type: "Q"}},
								Runtimes: []model.RuntimeSummary{{Count: 1, Runtime: 1}},
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

			Convey("with non-whitelisted master", func() {
				req := createTestUploadRequest(srv.URL, "non.whitelisted.master", frData)
				resp, err := client.Do(req)
				So(err, ShouldBeNil)
				defer resp.Body.Close()
				So(resp.StatusCode, ShouldEqual, http.StatusBadRequest)
			})

			// Regression test: timestamp 1500791325552 was reported by one of the
			// test launchers and that broke our #plx pipelines.
			Convey("with invalid timestamp value", func() {
				frData := bytes.Replace(
					frData, []byte("1406123456.0"), []byte("1500791325552.0"), 1)
				req := createTestUploadRequest(srv.URL, "chromium.chromiumos", frData)
				resp, err := client.Do(req)
				So(err, ShouldBeNil)
				defer resp.Body.Close()
				So(resp.StatusCode, ShouldEqual, http.StatusBadRequest)
			})
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
				datastore.GetTestable(ctx).CatchupIndexes()
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
			datastore.GetTestable(ctx).AddIndexes(idx...)
			datastore.GetTestable(ctx).CatchupIndexes()

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
			So(datastore.Put(ctx, &resultsTf), ShouldBeNil)

			incr := model.AggregateResult{
				Builder: "Linux Swarm",
				BuilderInfo: &model.BuilderInfo{
					BuildNumbers:   []model.Number{7399},
					FailuresByType: map[string][]int{"PASS": {1}},
					Tests:          model.AggregateTest{},
				},
			}

			Convey("valid aggregate entity", func() {
				datastore.GetTestable(ctx).CatchupIndexes()
				So(updateIncremental(SetUploadParams(ctx, &UploadParams{
					Master:   "chromium.swarm",
					TestType: "content_unittests",
					Builder:  "Linux Swarm",
				}), &incr), ShouldBeNil)

				datastore.GetTestable(ctx).CatchupIndexes()
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
				So(len(updated.BuilderInfo.BuildNumbers), ShouldEqual, 500)
				So(updated.BuilderInfo.BuildNumbers[0], ShouldEqual, 7399)
				So(len(updated.BuilderInfo.FailuresByType["PASS"]), ShouldEqual, 501)
				So(updated.Builder, ShouldEqual, "Linux Swarm")
			})

			Convey("corrupted aggregate entity: mismatching builder name", func() {
				resultsTf.Builder = "" // Mistamach with "Linux Swarm" stored in JSON.
				So(datastore.Put(ctx, &resultsTf), ShouldBeNil)

				datastore.GetTestable(ctx).CatchupIndexes()
				So(updateIncremental(SetUploadParams(ctx, &UploadParams{
					Master:   "chromium.swarm",
					TestType: "content_unittests",
					Builder:  "Linux Swarm",
				}), &incr), ShouldBeNil)

				datastore.GetTestable(ctx).CatchupIndexes()
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
				So(updated, ShouldResemble, incr)
			})
		})
	})
}

func TestUses409ResponseCodeForBuildNumberConflict(t *testing.T) {
	t.Parallel()

	Convey("Return HTTP response code 409 for build with same number", t, func() {
		ctx := memory.Use(context.Background())
		testFileIdx, err := datastore.FindAndParseIndexYAML(
			filepath.Join("testdata"))
		if err != nil {
			panic(err)
		}
		datastore.GetTestable(ctx).AddIndexes(testFileIdx...)
		datastore.GetTestable(ctx).CatchupIndexes()

		ctx = SetUploadParams(ctx, &UploadParams{
			Master:   "foo",
			Builder:  "test-builder",
			TestType: "baz",
		})
		data, err := ioutil.ReadFile(
			filepath.Join("testdata", "full_results_0.json"))
		data = bytes.TrimSpace(data)
		So(err, ShouldBeNil)

		So(updateFullResults(ctx, bytes.NewReader(data)), ShouldBeNil)

		// Ensure that the file is saved in datastore. See http://crbug.com/648817.
		datastore.GetTestable(ctx).CatchupIndexes()

		err = updateFullResults(ctx, bytes.NewReader(data))
		se, ok := err.(statusError)
		So(ok, ShouldBeTrue)
		So(se.code, ShouldEqual, 409)
	})
}
