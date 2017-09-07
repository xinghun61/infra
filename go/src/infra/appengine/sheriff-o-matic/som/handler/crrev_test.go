package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/client/test"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRevRangeHandler(t *testing.T) {
	fakeCrRev := test.NewFakeServer()
	defer fakeCrRev.Server.Close()

	c := gaetesting.TestingContext()
	c = gologger.StdConfig.Use(c)
	c = client.WithCrRev(c, fakeCrRev.Server.URL)

	Convey("get rev range", t, func() {
		Convey("ok", func() {
			c = authtest.MockAuthConfig(c)
			w := httptest.NewRecorder()
			GetRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("start", "123", "end", "456"),
			})

			So(w.Code, ShouldEqual, 301)
		})
		Convey("bad oauth", func() {
			w := httptest.NewRecorder()
			GetRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("start", "123", "end", "456"),
			})
			So(w.Code, ShouldEqual, http.StatusMovedPermanently)
		})
		Convey("bad request", func() {
			w := httptest.NewRecorder()

			GetRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
			})

			So(w.Code, ShouldEqual, 400)
		})
	})
}
