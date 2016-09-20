// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"errors"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/memcache"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"

	"infra/appengine/test-results/builderstate"
)

func TestBuilderState(t *testing.T) {
	t.Parallel()

	testCtx := memory.Use(context.Background())
	WithTestingContext := func(c *router.Context, next router.Handler) {
		c.Context = testCtx
		next(c)
	}
	r := router.New()
	mw := router.NewMiddlewareChain(WithTestingContext)
	r.GET("/builderstate", mw, getBuilderStateHandler)
	r.GET("/updatebuilderstate", mw, updateBuilderStateHandler)

	srv := httptest.NewServer(r)
	client := &http.Client{}

	Convey("BuilderState", t, func() {
		bsJSON := []byte(`{"masters":[]}`)
		refreshed := false

		Convey("GET /builderstate", func() {
			Convey("cache miss, refresh fails: returns HTTP status 500", func() {
				refreshFunc = func(c context.Context) (memcache.Item, error) {
					refreshed = true
					return nil, errors.New("mock refreshFunc: refresh fail")
				}

				resp, err := client.Get(srv.URL + "/builderstate")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, http.StatusInternalServerError)
				So(refreshed, ShouldBeTrue)
			})

			Convey("cache miss, refresh success: HTTP status 200", func() {
				refreshFunc = func(c context.Context) (memcache.Item, error) {
					refreshed = true
					n := memcache.NewItem(c, builderstate.MemcacheKey)
					n.SetValue(bsJSON)
					return n, nil
				}

				resp, err := client.Get(srv.URL + "/builderstate")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, http.StatusOK)
				So(refreshed, ShouldBeTrue)
				data, err := ioutil.ReadAll(resp.Body)
				defer resp.Body.Close()
				So(err, ShouldBeNil)
				So(data, ShouldResemble, bsJSON)
			})

			Convey("cache hit: HTTP status 200 and does not call refreshFunc", func() {
				item := memcache.NewItem(testCtx, builderstate.MemcacheKey)
				item.SetValue(bsJSON)
				memcache.Set(testCtx, item)

				refreshFunc = func(c context.Context) (memcache.Item, error) {
					refreshed = true
					return nil, errors.New("mock refreshFunc: generic error")
				}

				resp, err := client.Get(srv.URL + "/builderstate")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, http.StatusOK)
				So(refreshed, ShouldBeFalse)
				data, err := ioutil.ReadAll(resp.Body)
				defer resp.Body.Close()
				So(err, ShouldBeNil)
				So(data, ShouldResemble, bsJSON)
			})
		})

		Convey("GET /updatebuilderstate", func() {
			Convey("refresh fails", func() {
				refreshFunc = func(c context.Context) (memcache.Item, error) {
					refreshed = true
					return nil, errors.New("mock refreshFunc: refresh fail")
				}

				resp, err := client.Get(srv.URL + "/updatebuilderstate")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, http.StatusInternalServerError)
				So(refreshed, ShouldBeTrue)
			})

			Convey("refresh success", func() {
				refreshFunc = func(c context.Context) (memcache.Item, error) {
					refreshed = true
					return memcache.NewItem(c, builderstate.MemcacheKey), nil
				}

				resp, err := client.Get(srv.URL + "/updatebuilderstate")
				So(err, ShouldBeNil)
				So(resp.StatusCode, ShouldEqual, http.StatusOK)
				So(refreshed, ShouldBeTrue)
				data, err := ioutil.ReadAll(resp.Body)
				defer resp.Body.Close()
				So(err, ShouldBeNil)
				So(string(data), ShouldResemble, "OK")
			})
		})
	})
}
