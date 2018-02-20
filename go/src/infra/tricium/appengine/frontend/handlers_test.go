// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"net/url"
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

func TestFormRequests(t *testing.T) {
	Convey("Test Environment", t, func() {
		project := "test-project"
		gitRef := "ref/test"
		paths := []string{
			"README.md",
			"README2.md",
		}

		Convey("Form request", func() {
			v := url.Values{}

			Convey("Is successfully parsed when complete", func() {
				v.Set("Project", project)
				v.Set("GitRef", gitRef)
				v["Path[]"] = paths
				sr, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldBeNil)
				So(sr.Project, ShouldEqual, project)
				So(sr.GitRef, ShouldEqual, gitRef)
				So(len(sr.Paths), ShouldEqual, len(paths))
				for k, p := range paths {
					So(sr.Paths[k], ShouldEqual, p)
				}
			})

			Convey("Fails with missing project", func() {
				v.Set("GitRef", gitRef)
				v["Path[]"] = paths
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})

			Convey("Fails with missing Git ref", func() {
				v.Set("Project", project)
				v["Path[]"] = paths
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})

			Convey("Fails with missing paths", func() {
				v.Set("Project", project)
				v.Set("GitRef", gitRef)
				_, err := parseRequestForm(&http.Request{Form: v})
				So(err, ShouldNotBeNil)
			})
		})
	})
}
