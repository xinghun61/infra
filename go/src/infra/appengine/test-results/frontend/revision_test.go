// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/server/router"
)

func TestRevisionHandler(t *testing.T) {
	t.Parallel()

	data := map[string][]byte{
		"500": []byte("invalid json"),
		"1300": []byte(
			`{
         "git_sha": "0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f",
         "repo": "chromium/src",
         "redirect_url": "https://chromium.googlesource.com/chromium/src/+/0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f",
         "project": "chromium",
         "redirect_type": "GIT_FROM_NUMBER",
         "repo_url": "https://chromium.googlesource.com/chromium/src/",
         "kind": "crrev#redirectItem",
         "etag": "\"kuKkspxlsT40mYsjSiqyueMe20E/qt8_sNqlQbK8xP9pkpc9EOsNyrE\""
       }`),
		"1350": []byte(
			`{
         "git_sha": "2a2d3d036c39043ef5f8232493252732a17f7e16",
         "repo": "chromium/src",
         "redirect_url": "https://chromium.googlesource.com/chromium/src/+/0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f",
         "project": "chromium",
         "redirect_type": "GIT_FROM_NUMBER",
         "repo_url": "https://chromium.googlesource.com/chromium/src/",
         "kind": "crrev#redirectItem",
         "etag": "\"kuKkspxlsT40mYsjSiqyueMe20E/qt8_sNqlQbK8xP9pkpc9EOsNyrE\""
       }`),
	}

	handler := func(c *router.Context) {
		b, ok := data[c.Params.ByName("pos")]
		if !ok {
			http.Error(c.Writer, "not found", http.StatusNotFound)
			return
		}
		c.Writer.Write(b)
	}

	ctx := memory.Use(context.Background())
	withTestingContext := func(c *router.Context, next router.Handler) {
		c.Context = ctx
		next(c)
	}

	r := router.New()
	r.GET(
		"/revision_range", router.NewMiddlewareChain(withTestingContext),
		revisionHandler)
	r.GET("/commitHash/:pos", router.MiddlewareChain{}, handler)
	srv := httptest.NewServer(r)
	crRevURL = srv.URL + "/commitHash"

	Convey("commitHash", t, func() {
		client := crRevClient{
			HTTPClient: &http.Client{},
			BaseURL:    crRevURL,
		}

		Convey("with existing position", func() {
			hash, err := client.commitHash("1300")
			So(err, ShouldBeNil)
			So(hash, ShouldEqual, "0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f")
		})

		Convey("with non-existent position", func() {
			_, err := client.commitHash("0")
			So(err, ShouldNotBeNil)
		})

		Convey("with invalid returned JSON", func() {
			_, err := client.commitHash("500")
			So(err, ShouldNotBeNil)
		})

		Convey("with HTTP error", func() {
			client.BaseURL = "invalid-url"
			_, err := client.commitHash("500")
			So(err, ShouldNotBeNil)
		})
	})

	Convey("revisionHandler", t, func() {
		ctx = urlfetch.Set(ctx, http.DefaultTransport)

		client := &http.Client{
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return http.ErrUseLastResponse
			},
		}

		Convey("with valid range", func() {
			resp, err := client.Get(
				srv.URL + "/revision_range?start=1300&end=1350&n=1000")
			So(err, ShouldBeNil)
			defer resp.Body.Close()

			So(resp.StatusCode, ShouldEqual, http.StatusMovedPermanently)
			So(resp.Header.Get("Location"), ShouldEqual,
				"https://chromium.googlesource.com/chromium/src/+log/"+
					"0dfc81bbe403cd98f4cd2d58e7817cdc8a881a5f^.."+
					"2a2d3d036c39043ef5f8232493252732a17f7e16?pretty=fuller&n=1000")
		})

		Convey("with invalid range", func() {
			resp, err := client.Get(srv.URL + "/revision_range?start=0&end=100")
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusInternalServerError)
		})
	})
}
