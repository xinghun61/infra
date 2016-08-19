// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"bytes"
	"infra/appengine/test-results/model"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"
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
		ds := datastore.Get(ctx)

		dataEntries := []model.DataEntry{
			{Data: []byte("foo"), ID: 1},
			{Data: []byte("bar"), ID: 2},
			{Data: []byte("baz"), ID: 3},
			{Data: []byte("qux"), ID: 4},
		}
		for _, de := range dataEntries {
			So(ds.Put(&de), ShouldBeNil)
		}
		dataKeys := make([]*datastore.Key, len(dataEntries))
		for i, de := range dataEntries {
			dataKeys[i] = ds.KeyForObj(&de)
		}
		tf := model.TestFile{
			ID:       1,
			DataKeys: dataKeys,
		}
		So(ds.Put(&tf), ShouldBeNil)

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			ds.Testable().CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.GET("/testfile", router.NewMiddlewareChain(withTestingContext), getHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		Convey("respondTestFileData", func() {
			Convey("succeeds", func() {
				resp, err := client.Get(srv.URL + "/testfile?key=" + ds.KeyForObj(&tf).Encode())
				So(err, ShouldBeNil)
				defer resp.Body.Close()
				b, err := ioutil.ReadAll(resp.Body)
				So(err, ShouldBeNil)
				So(string(b), ShouldEqual, "foobarbazqux")
			})
		})
	})
}
