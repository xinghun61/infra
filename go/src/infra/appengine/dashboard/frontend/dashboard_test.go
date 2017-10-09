// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dashboard

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/julienschmidt/httprouter"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"

	. "github.com/smartystreets/goconvey/convey"
)

func TestDashboard(t *testing.T) {
	t.Parallel()

	Convey("dashboard", t, func() {
		c := gaetesting.TestingContext()
		c = gologger.StdConfig.Use(c)

		w := httptest.NewRecorder()

		Convey("template params", func() {
			Convey("anonymous", func() {
				dashboard(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "/"),
				})
				So(w.Code, ShouldEqual, 500)
			})

			authState := &authtest.FakeState{
				Identity: "user:user@example.com",
			}
			c = auth.WithState(c, authState)
			c = templates.Use(c, templateBundle)

			Convey("not-googler", func() {
				dashboard(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "/"),
				})

				r, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				body := string(r)
				So(body, ShouldContainSubstring, "chopsdash-app")
				So(w.Code, ShouldEqual, 200)
				So(body, ShouldNotContainSubstring, "is-googler")
				So(body, ShouldContainSubstring, "user=\"user@example.com\"")
			})

			authState.IdentityGroups = []string{authGroup}
			Convey("googler", func() {
				dashboard(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "/"),
				})

				r, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				body := string(r)
				So(body, ShouldContainSubstring, "chopsdash-app")
				So(w.Code, ShouldEqual, 200)
				So(body, ShouldContainSubstring, "is-googler")
				So(body, ShouldContainSubstring, "user=\"user@example.com\"")
			})
		})
	})
}

func makeGetRequest() *http.Request {
	req, _ := http.NewRequest("GET", "/doesntmatter", nil)
	return req
}

func makeParams(items ...string) httprouter.Params {
	if len(items)%2 != 0 {
		return nil
	}

	params := make([]httprouter.Param, len(items)/2)
	for i := range params {
		params[i] = httprouter.Param{
			Key:   items[2*i],
			Value: items[2*i+1],
		}
	}

	return params
}
