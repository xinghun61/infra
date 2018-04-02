package handler

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/appengine/sheriff-o-matic/som/client/test"
	te "infra/appengine/sheriff-o-matic/som/testexpectations"

	"go.chromium.org/gae/impl/dummy"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

const (
	gitilesPrefix = "https://chromium.googlesource.com/chromium/src/+/master/"
)

// TODO(seanmccullough): Clean up this mocking mess.
type mck struct {
	giMock
}

func (m mck) ModuleHostname(a, b, c string) (string, error) {
	return "", nil
}

func TestGetLayoutTestsHandler(t *testing.T) {
	Convey("get layout tests", t, func() {
		c := gaetesting.TestingContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		gt := &testhelper.MockGitilesTransport{Responses: map[string]string{}}
		c = urlfetch.Set(c, gt)
		w := httptest.NewRecorder()

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
		}

		Convey("load all, error", func() {
			GetLayoutTestsHandler(ctx)

			So(w.Code, ShouldEqual, http.StatusInternalServerError)
		})

		Convey("load all, no error", func() {
			for _, path := range te.LayoutTestExpectations {
				gt.Responses[gitilesPrefix+path+"?format=TEXT"] = `unused`
			}
			GetLayoutTestsHandler(ctx)

			So(w.Code, ShouldEqual, http.StatusOK)
		})
	})
}

func TestPostLayoutTestExpectationChangeHandler(t *testing.T) {
	Convey("basic", t, func() {
		c := gaetesting.TestingContext()
		gt := &testhelper.MockGitilesTransport{Responses: map[string]string{}}
		for _, path := range te.LayoutTestExpectations {
			gt.Responses["https://chromium.googlesource.com/chromium/src/+/master/"+path+"?format=TEXT"] = ""
		}

		c = urlfetch.Set(c, gt)

		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return mck{giMock{dummy.Info(), "", time.Now(), nil}}
		})

		Convey("empty body, error", func() {
			w := httptest.NewRecorder()
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makePostRequest(""),
			}

			PostLayoutTestExpectationChangeHandler(ctx)
			So(w.Code, ShouldEqual, http.StatusInternalServerError)
		})

		Convey("valid body", func() {
			w := httptest.NewRecorder()
			body, err := json.Marshal(&shortExp{
				TestName: "test_test/test.html",
			})
			So(err, ShouldBeNil)
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makePostRequest(string(body)),
			}

			PostLayoutTestExpectationChangeHandler(ctx)
			So(w.Code, ShouldNotEqual, http.StatusInternalServerError)
		})
	})
}
