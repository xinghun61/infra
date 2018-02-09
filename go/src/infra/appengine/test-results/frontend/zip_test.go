package frontend

import (
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"

	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func makeGetRequest() *http.Request {
	req, err := http.NewRequest("GET", "/doesntmatter", nil)
	if err != nil {
		panic(err)
	}
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

func TestGetZipHandler(t *testing.T) {
	Convey("get zip handler", t, func() {
		oldZipFile := getZipFile
		zipRes := []byte{}
		var zipErr error
		getZipFile = func(c context.Context, builder, buildNum, filepath string) ([]byte, error) {
			return zipRes, zipErr
		}

		c := gaetesting.TestingContext()
		w := httptest.NewRecorder()

		ctx := &router.Context{
			Context: c,
			Writer:  w,
			Request: makeGetRequest(),
			Params:  makeParams("builder", "test_builder", "buildnum", "123", "filepath", "a/b/c"),
		}

		Convey("404", func() {
			zipRes = nil
			getZipHandler(ctx)

			bytes, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			So(bytes, ShouldResemble, []byte("not found"))
			So(w.Code, ShouldEqual, http.StatusNotFound)
		})

		Convey("success", func() {
			zipRes = []byte("abcde")
			getZipHandler(ctx)

			bytes, err := ioutil.ReadAll(w.Body)
			So(err, ShouldBeNil)
			So(bytes, ShouldResemble, []byte("abcde"))
			So(w.Code, ShouldEqual, http.StatusOK)

		})

		getZipFile = oldZipFile
	})
}
