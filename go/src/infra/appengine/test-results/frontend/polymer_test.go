// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPolymerHandler(t *testing.T) {
	t.Parallel()

	Convey("Test loading and serving of builder data.", t, func() {
		ctx := memory.Use(context.Background())

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			next(c)
		}

		Convey("polymerHander", func() {
			r := router.New()
			r.GET("/", router.NewMiddlewareChain(
				withTestingContext, templatesMiddleware()), polymerHandler)
			srv := httptest.NewServer(r)
			client := &http.Client{}

			resp, err := client.Get(srv.URL)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldContainSubstring, "<test-results></test-results>")
		})
	})
}
