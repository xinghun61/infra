package handler

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/client"
	"infra/appengine/sheriff-o-matic/som/client/mock"
	testhelper "infra/appengine/sheriff-o-matic/som/client/test"
	"infra/monitoring/messages"

	"go.chromium.org/gae/impl/dummy"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/server/router"

	"bytes"
	"compress/zlib"
	"net/url"
	"time"

	"github.com/golang/mock/gomock"
	. "github.com/smartystreets/goconvey/convey"
)

func TestLogDiffJSONHandler(t *testing.T) {
	Convey("ok request", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		data := []byte("testing string")
		var buffer bytes.Buffer
		writer := zlib.NewWriter(&buffer)
		writer.Write(data)
		writer.Close()
		logdiff := &LogDiff{
			Diffs:     buffer.Bytes(),
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  true,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "15038", "buildNum2", "15037"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad request with bad query", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		data := []byte("testing string")
		var buffer bytes.Buffer
		writer := zlib.NewWriter(&buffer)
		writer.Write(data)
		writer.Close()
		logdiff := &LogDiff{
			Diffs:     buffer.Bytes(),
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  true,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "15038", "buildNum2", "15036"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusNotFound)
	})

	Convey("bad request with bad diff data", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		header := []byte("bad test")
		logdiff := &LogDiff{
			Diffs:     header,
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  true,
			ID:        12345,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "15038", "buildNum2", "15037"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusInternalServerError)
	})
	Convey("bad request with bad build Num1", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		data := []byte("testing string")
		var buffer bytes.Buffer
		writer := zlib.NewWriter(&buffer)
		writer.Write(data)
		writer.Close()
		logdiff := &LogDiff{
			Diffs:     buffer.Bytes(),
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  true,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "bad number", "buildNum2", "15037"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusInternalServerError)
	})
	Convey("bad request with bad build Num2", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		data := []byte("testing string")
		var buffer bytes.Buffer
		writer := zlib.NewWriter(&buffer)
		writer.Write(data)
		writer.Close()
		logdiff := &LogDiff{
			Diffs:     buffer.Bytes(),
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  true,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "15038", "buildNum2", "bad number"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusInternalServerError)
	})
	Convey("bad request with incomplete diffs", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", clock.Now(c), nil}
		})
		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		data := []byte("testing string")
		var buffer bytes.Buffer
		writer := zlib.NewWriter(&buffer)
		writer.Write(data)
		writer.Close()
		logdiff := &LogDiff{
			Diffs:     buffer.Bytes(),
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  false,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)
		w := httptest.NewRecorder()
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("master", "chromium.test", "builder", "test", "buildNum1", "15038", "buildNum2", "15037"),
		}
		LogDiffJSONHandler(ctx)
		So(w.Code, ShouldEqual, http.StatusNotFound)
	})
}

func TestLogdiffWorker(t *testing.T) {
	Convey("ok request", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		c = setUpGitiles(c)
		mockCtrl := gomock.NewController(t)
		bbMock := mock.NewMockBuildbotClient(mockCtrl)
		biMock := mock.NewMockBuildInfoClient(mockCtrl)
		c = client.WithMiloBuildbot(c, bbMock)
		c = client.WithMiloBuildInfo(c, biMock)

		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		logdiff := &LogDiff{
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  false,
			ID:        12345,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)

		w := httptest.NewRecorder()
		values := url.Values{}
		values.Set("lastFail", "15038")
		values.Set("lastPass", "15037")
		values.Set("master", "chromium.test")
		values.Set("builder", "test")
		values.Set("ID", "12345")
		r := makePostRequest(values.Encode())
		r.PostForm = values

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: r,
			Params:  nil,
		}
		LogdiffWorker(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad request with bad fail values", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		c = setUpGitiles(c)
		mockCtrl := gomock.NewController(t)
		bbMock := mock.NewMockBuildbotClient(mockCtrl)
		biMock := mock.NewMockBuildInfoClient(mockCtrl)
		c = client.WithMiloBuildbot(c, bbMock)
		c = client.WithMiloBuildInfo(c, biMock)

		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		logdiff := &LogDiff{
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  false,
			ID:        12345,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)

		w := httptest.NewRecorder()
		values := url.Values{}
		values.Set("lastFail", "")
		values.Set("lastPass", "15037")
		values.Set("master", "chromium.test")
		values.Set("builder", "test")
		values.Set("ID", "12345")
		r := makePostRequest(values.Encode())
		r.PostForm = values

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: r,
			Params:  nil,
		}
		LogdiffWorker(ctx)

		So(w.Code, ShouldEqual, http.StatusInternalServerError)
	})

	Convey("bad request with bad pass values", t, func() {
		c := newTestContext()
		c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
			return giMock{dummy.Info(), "", time.Now(), nil}
		})
		c = setUpGitiles(c)
		mockCtrl := gomock.NewController(t)
		bbMock := mock.NewMockBuildbotClient(mockCtrl)
		biMock := mock.NewMockBuildInfoClient(mockCtrl)
		c = client.WithMiloBuildbot(c, bbMock)
		c = client.WithMiloBuildInfo(c, biMock)

		c = client.WithReader(c, testhelper.MockReader{
			StdioForStepValue: []string{" ", " "},
			BuildExtracts: map[string]*messages.BuildExtract{
				"chromium": {},
			},
		})

		q := datastore.NewQuery("LogDiff")
		results := []*LogDiff{}
		So(datastore.GetAll(c, q, &results), ShouldBeNil)
		So(results, ShouldBeEmpty)
		logdiff := &LogDiff{
			Master:    "chromium.test",
			Builder:   "test",
			BuildNum1: 15038,
			BuildNum2: 15037,
			Complete:  false,
			ID:        12345,
		}
		So(datastore.Put(c, logdiff), ShouldBeNil)

		w := httptest.NewRecorder()
		values := url.Values{}
		values.Set("lastFail", "15038")
		values.Set("lastPass", "")
		values.Set("master", "chromium.test")
		values.Set("builder", "test")
		values.Set("ID", "12345")
		r := makePostRequest(values.Encode())
		r.PostForm = values

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: r,
			Params:  nil,
		}
		LogdiffWorker(ctx)

		So(w.Code, ShouldEqual, http.StatusInternalServerError)
	})
}
