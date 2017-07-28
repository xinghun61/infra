package som

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"infra/monitoring/client"
	"infra/monitoring/client/test"

	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/router"

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
