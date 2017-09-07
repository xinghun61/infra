package handler

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	"golang.org/x/net/context"

	testhelper "infra/appengine/sheriff-o-matic/som/client/test"
	te "infra/appengine/sheriff-o-matic/som/testexpectations"

	"go.chromium.org/gae/impl/dummy"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	tq "go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/gae/service/urlfetch"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"

	gerrit "github.com/andygrunwald/go-gerrit"
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
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return mck{giMock{dummy.Info(), "", time.Now(), nil}}
		})
		tqt := tq.GetTestable(c)
		tqt.CreateQueue(changeQueue)

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

func TestLayoutTestExpectationChangeWorker(t *testing.T) {
	Convey("basic", t, func() {
		c := gaetesting.TestingContext()
		c = gologger.StdConfig.Use(c)
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return mck{giMock{dummy.Info(), "", time.Now(), nil}}
		})
		gt := &testhelper.MockGitilesTransport{Responses: map[string]string{}}
		for _, path := range te.LayoutTestExpectations {
			gt.Responses[gitilesPrefix+path+"?format=TEXT"] = `unused`
		}

		c = urlfetch.Set(c, gt)
		c = authtest.MockAuthConfig(c)
		// Set up fake gerrit.
		testMux := http.NewServeMux()
		testServer := httptest.NewServer(testMux)
		c = withGerritInstance(c, testServer.URL)

		ta := datastore.GetTestable(c)
		ta.Consistent(true)

		testMux.HandleFunc("/a/changes/", func(w http.ResponseWriter, r *http.Request) {
			logging.Debugf(c, "gerrit req: %+v", r)
			switch r.Method {
			case "POST":
				marshalled, _ := json.Marshal(&gerrit.ChangeInfo{
					Project:  "project",
					Branch:   "branch",
					Subject:  "subject",
					Status:   "DRAFT",
					Topic:    "",
					ChangeID: "chromium~whatever1234",
					ID:       "1234",
				})
				fmt.Fprintf(w, ")]}'\n%s", string(marshalled))
				break
			case "PUT":
				w.WriteHeader(http.StatusOK)
				break
			default:
				w.WriteHeader(http.StatusBadRequest)
			}
		})

		tqt := tq.GetTestable(c)
		tqt.CreateQueue(changeQueue)

		Convey("empty body, error", func() {
			w := httptest.NewRecorder()
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makePostRequest(""),
			}

			LayoutTestExpectationChangeWorker(ctx)

			So(w.Code, ShouldEqual, http.StatusBadRequest)
		})

		Convey("valid body, no queued update entity", func() {
			w := httptest.NewRecorder()
			expJSON, err := json.Marshal(&shortExp{
				TestName: "test_test/test.html",
			})
			So(err, ShouldBeNil)
			values := url.Values{}
			values.Set("change", string(expJSON))
			values.Set("requester", "me@domain.com")
			values.Set("updateID", "\u0001")
			r := makePostRequest(values.Encode())

			r.PostForm = values
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: r,
			}
			logging.Errorf(c, "values: %+v", values.Encode())
			LayoutTestExpectationChangeWorker(ctx)
			So(w.Code, ShouldEqual, http.StatusBadRequest)
		})

		Convey("valid body, valid queued update entity", func() {
			w := httptest.NewRecorder()
			expJSON, err := json.Marshal(&shortExp{
				TestName: "test_test/test.html",
			})
			So(err, ShouldBeNil)

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

			values := url.Values{}
			values.Set("change", string(expJSON))
			values.Set("requester", "me@domain.com")
			values.Set("updateID", "\u0001")
			r := makePostRequest(values.Encode())

			r.PostForm = values
			ctx = &router.Context{
				Context: c,
				Writer:  w,
				Request: r,
			}
			logging.Errorf(c, "values: %+v", values.Encode())
			LayoutTestExpectationChangeWorker(ctx)
			So(w.Code, ShouldNotEqual, http.StatusInternalServerError)
		})
	})
}
