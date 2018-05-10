// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/golang/protobuf/proto"
	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	"infra/tricium/api/v1"
	"infra/tricium/appengine/common/triciumtest"
)

func TestLandingPageHandler(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &triciumtest.Testing{}
		ctx := tt.Context()

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			next(c)
		}

		r := router.New()
		mw := router.NewMiddlewareChain(withTestingContext)
		mw = mw.Extend(templates.WithTemplates(&templates.Bundle{
			Loader: templates.AssetsLoader(map[string]string{
				"pages/index.html": "Landing page content",
			}),
		}))
		r.GET("/", mw, landingPageHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		Convey("Basic request", func() {
			resp, err := client.Get(srv.URL + "/")
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "Landing page content")
		})
	})
}

func TestAnalyzeQueueHandler(t *testing.T) {
	Convey("Test Environment", t, func() {
		tt := &triciumtest.Testing{}
		ctx := tt.Context()

		w := httptest.NewRecorder()

		Convey("Analyze queue handler checks for invalid requests", func() {
			// A request with an empty paths list is not valid.
			ar := &tricium.AnalyzeRequest{
				Project: "some-project",
				GitRef:  "some/ref",
				Paths:   nil,
			}
			bytes, err := proto.Marshal(ar)
			analyzeHandler(&router.Context{
				Context: ctx,
				Writer:  w,
				Request: triciumtest.MakeGetRequest(bytes),
				Params:  triciumtest.MakeParams(),
			})
			So(w.Code, ShouldEqual, 400)
			r, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			body := string(r)
			So(body, ShouldEqual, "")
		})
	})
}
