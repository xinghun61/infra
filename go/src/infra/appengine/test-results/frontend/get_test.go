// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"encoding/json"
	"html/template"
	"infra/appengine/test-results/model"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	. "github.com/smartystreets/goconvey/convey"
)

func TestWrapCallback(t *testing.T) {
	t.Parallel()

	Convey("wrapCallback", t, func() {
		expected := []byte(`foo({"hello":"world"});`)
		result := wrapCallback(
			bytes.NewReader([]byte(`{"hello":"world"}`)),
			"foo",
		)
		b, err := ioutil.ReadAll(result)
		So(err, ShouldBeNil)
		So(b, ShouldResemble, expected)
	})
}

func TestGetHandler(t *testing.T) {
	t.Parallel()

	Convey("getHandler", t, func() {
		ctx := memory.Use(context.Background())

		dataEntries := []model.DataEntry{
			{Data: []byte("foo"), ID: 1},
			{Data: []byte("bar"), ID: 2},
			{Data: []byte("baz"), ID: 3},
			{Data: []byte("qux"), ID: 4},
		}
		for _, de := range dataEntries {
			So(datastore.Put(ctx, &de), ShouldBeNil)
		}
		dataKeys := make([]*datastore.Key, len(dataEntries))
		for i, de := range dataEntries {
			dataKeys[i] = datastore.KeyForObj(ctx, &de)
		}
		tf := model.TestFile{
			Name:        "full_results.json",
			Master:      "tryserver.chromium.mac",
			Builder:     "mac_chromium_rel_ng",
			BuildNumber: 123,
			TestType:    "pixel_test (with patch)",
			DataKeys:    dataKeys,
		}
		So(datastore.Put(ctx, &tf), ShouldBeNil)

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			datastore.GetTestable(ctx).Consistent(true)
			datastore.GetTestable(ctx).AutoIndex(true)
			datastore.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.GET("/testfile", router.NewMiddlewareChain(withTestingContext), getHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		Convey("respondTestFileData", func() {
			resp, err := client.Get(srv.URL + "/testfile?key=" + datastore.KeyForObj(ctx, &tf).Encode())
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "foobarbazqux")
		})

		Convey("respondTestFileDefault", func() {
			testURL, err := url.Parse(srv.URL)
			So(err, ShouldBeNil)
			testURL.Path = "/testfile"
			testURL.RawQuery = url.Values{
				"name":        {"full_results.json"},
				"master":      {"tryserver.chromium.mac"},
				"builder":     {"mac_chromium_rel_ng"},
				"buildnumber": {"123"},
				"testtype":    {"pixel_test (with patch)"},
			}.Encode()
			resp, err := client.Get(testURL.String())
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "foobarbazqux")
		})

		Convey("respondTestFileDefault with full step name", func() {
			testURL, err := url.Parse(srv.URL)
			So(err, ShouldBeNil)
			testURL.Path = "/testfile"
			testURL.RawQuery = url.Values{
				"name":        {"full_results.json"},
				"master":      {"tryserver.chromium.mac"},
				"builder":     {"mac_chromium_rel_ng"},
				"buildnumber": {"123"},
				"testtype":    {"pixel_test on Intel GPU on Mac (with patch)"},
			}.Encode()
			resp, err := client.Get(testURL.String())
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "foobarbazqux")
		})
	})

	Convey("getHandler::respondTestFileList", t, func() {
		ctx := memory.Use(context.Background())

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			datastore.GetTestable(ctx).Consistent(true)
			datastore.GetTestable(ctx).AutoIndex(true)
			datastore.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		mw := router.NewMiddlewareChain(withTestingContext)
		mw = mw.Extend(templates.WithTemplates(&templates.Bundle{
			Loader: templates.AssetsLoader(map[string]string{
				"pages/showfilelist.html": "{{ . | dumpJSON }}",
			}),
			FuncMap: template.FuncMap{
				"dumpJSON": func(v interface{}) (string, error) {
					b, e := json.Marshal(v)
					return string(b), e
				},
			},
		}))
		r.GET("/testfile", mw, getHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		// Add two files from tryserver.chromium.mac to be returned for the query
		// below.
		So(datastore.Put(ctx, &model.TestFile{
			Name:        "full_results.json",
			Master:      "tryserver.chromium.mac",
			Builder:     "mac_chromium_rel_ng",
			BuildNumber: 123,
			TestType:    "pixel_test (with patch)",
		}), ShouldBeNil)

		So(datastore.Put(ctx, &model.TestFile{
			Name:        "full_results.json",
			Master:      "tryserver.chromium.mac",
			Builder:     "mac_chromium_rel_ng",
			BuildNumber: 124,
			TestType:    "pixel_test (with patch)",
		}), ShouldBeNil)

		// Add a file from trysever.chromium.linux to check this it is correctly
		// skipped by the query below.
		So(datastore.Put(ctx, &model.TestFile{
			Name:        "full_results.json",
			Master:      "tryserver.chromium.linux",
			Builder:     "linux_chromium_rel_ng",
			BuildNumber: 121,
			TestType:    "pixel_test (with patch)",
		}), ShouldBeNil)

		// Query for builds from tryserver.chromium.mac.
		testURL, err := url.Parse(srv.URL)
		So(err, ShouldBeNil)
		testURL.Path = "/testfile"
		testURL.RawQuery = url.Values{"master": {"tryserver.chromium.mac"}}.Encode()
		resp, err := client.Get(testURL.String())
		So(err, ShouldBeNil)
		defer resp.Body.Close()
		b, err := ioutil.ReadAll(resp.Body)
		So(err, ShouldBeNil)
		s := strings.Replace(string(b), "&#34;", "\"", -1) // unescape "
		So(s, ShouldContainSubstring, `"BuildNumber":123`)
		So(s, ShouldContainSubstring, `"BuildNumber":124`)
		So(s, ShouldNotContainSubstring, `"BuildNumber":121`)
	})

}
