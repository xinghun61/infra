package som

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	testhelper "infra/monitoring/analyzer/test"
	"infra/monitoring/messages"

	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestPostMiloPubSubHandler(t *testing.T) {
	Convey("bad push request", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		msg := "invalid json"
		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(msg),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad message data", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: []byte("invalid data")}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("bad message build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write([]byte("invalid build extract"))
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("good message empty build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		bmm := buildMasterMsg{
			Master: &messages.BuildExtract{},
			Builds: []*messages.Build{},
		}
		bmmJSON, err := json.Marshal(bmm)
		So(err, ShouldBeNil)

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write(bmmJSON)
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})

	Convey("good message non-empty build extract", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		bf := testhelper.NewBuilderFaker("fake.master", "fake.builder")
		bf.Build(0).Step("steps").Results(0).BuildFaker.Step("compile").Results(0)

		bmm := buildMasterMsg{
			Master: &messages.BuildExtract{},
			Builds: bf.GetBuilds(),
		}
		bmmJSON, err := json.Marshal(bmm)
		So(err, ShouldBeNil)

		var b bytes.Buffer
		zw := zlib.NewWriter(&b)
		zw.Write(bmmJSON)
		zw.Close()

		msg, err := json.Marshal(pushRequest{Message: pushMessage{Data: b.Bytes()}})
		So(err, ShouldBeNil)

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makePostRequest(string(msg)),
			Params:  makeParams("path", ""),
		}
		postMiloPubSubHandler(ctx)

		So(w.Code, ShouldEqual, http.StatusOK)
	})
}

func TestGetPubSubAlertsHandler(t *testing.T) {
	t.Parallel()
	Convey("main", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = auth.SetAuthenticator(c, []auth.Method(nil))
		c = urlfetch.Set(c, http.DefaultTransport)

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		So(w.Code, ShouldEqual, 200)
	})

	Convey("error getting gatekeeper trees", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = auth.SetAuthenticator(c, []auth.Method(nil))
		c = urlfetch.Set(c, http.DefaultTransport)

		oldGetGKTrees := getGatekeeperTrees

		getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
			return nil, fmt.Errorf("failure")
		}

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		getGatekeeperTrees = oldGetGKTrees
		So(w.Code, ShouldEqual, 500)
	})

	Convey("unrecognized gatekeeper tree", t, func() {
		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()
		c = auth.SetAuthenticator(c, []auth.Method(nil))
		c = urlfetch.Set(c, http.DefaultTransport)

		oldGetGKTrees := getGatekeeperTrees

		getGatekeeperTrees = func(c context.Context) (map[string]*messages.TreeMasterConfig, error) {
			return map[string]*messages.TreeMasterConfig{"foo": nil}, nil
		}

		getPubSubAlertsHandler(&router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("tree", "chromium"),
		})

		getGatekeeperTrees = oldGetGKTrees
		So(w.Code, ShouldEqual, 404)
	})
}
