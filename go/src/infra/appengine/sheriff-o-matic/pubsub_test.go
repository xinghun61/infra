package som

import (
	"bytes"
	"compress/zlib"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	testhelper "infra/monitoring/analyzer/test"
	"infra/monitoring/messages"

	"github.com/luci/luci-go/appengine/gaetesting"
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
