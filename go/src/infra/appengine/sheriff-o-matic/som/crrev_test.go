package som

import (
	"encoding/json"
	"infra/monitoring/client"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/logging/gologger"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRevRangeHandler(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		data, err := json.Marshal(map[string]string{"a": "b"})
		if err != nil {
			t.Errorf("couldn't marshal json data")
		}
		w.Write(data)
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	c := gaetesting.TestingContext()
	c = gologger.StdConfig.Use(c)

	Convey("get rev range", t, func() {
		Convey("ok", func() {
			c = authtest.MockAuthConfig(c)
			c = client.WithCrRev(c, server.URL)
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
			c := gaetesting.TestingContext()
			c = client.WithCrRev(c, server.URL)
			w := httptest.NewRecorder()
			GetRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("start", "123", "end", "456"),
			})
			So(w.Code, ShouldEqual, http.StatusInternalServerError)
		})
		Convey("bad request", func() {
			c := gaetesting.TestingContext()
			c = authtest.MockAuthConfig(c)
			c = client.WithCrRev(c, server.URL)
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
