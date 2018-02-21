// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	trit "infra/tricium/appengine/common/testing"
)

func TestLandingPageHandler(t *testing.T) {
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
