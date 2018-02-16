package frontend

import (
	"archive/zip"
	"bytes"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/gcloud/gs"
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

func TestGetZipFile(t *testing.T) {
	Convey("get zip file", t, func() {
		c := gaetesting.TestingContext()

		var zipErr error
		fileContents := map[string]string{}
		oldReadZip := readZipFile
		readZipFile = func(c context.Context, gsPath gs.Path) (*zip.Reader, error) {
			if zipErr != nil {
				return nil, zipErr
			}

			return makeZip(fileContents), nil
		}

		Convey("404", func() {
			res, err := getZipFile(c, "test_builder", "123", "file.txt")
			So(err, ShouldBeNil)
			So(res, ShouldBeNil)
		})

		itm := memcache.NewItem(c, "gs://chromium-layout-test-archives/test_builder/123/layout-test-results.zip|file.txt")
		Convey("file found", func() {
			fileContents["file.txt"] = "hi"
			res, err := getZipFile(c, "test_builder", "123", "file.txt")
			So(err, ShouldBeNil)
			So(res, ShouldResemble, []byte("hi"))
		})

		Convey("memcache", func() {
			itm.SetValue([]byte("hi"))
			So(memcache.Set(c, itm), ShouldBeNil)
			// Make sure that no network RPC happens
			zipErr = fmt.Errorf("This should not show up")

			res, err := getZipFile(c, "test_builder", "123", "file.txt")
			So(err, ShouldBeNil)
			So(res, ShouldResemble, []byte("hi"))
		})

		readZipFile = oldReadZip
	})
}

// Makes a zip from a map of filename to contents. Doesn't validate input, panics on
// any error.
func makeZip(fileContents map[string]string) *zip.Reader {
	buf := new(bytes.Buffer)
	zw := zip.NewWriter(buf)
	for fname, contents := range fileContents {
		w, err := zw.Create(fname)
		if err != nil {
			panic(err)
		}
		_, err = w.Write([]byte(contents))
		if err != nil {
			panic(err)
		}
	}
	err := zw.Close()
	if err != nil {
		panic(err)
	}

	zipRes, err := zip.NewReader(bytes.NewReader(buf.Bytes()), int64(buf.Len()))
	if err != nil {
		panic(err)
	}
	return zipRes
}

func TestCacheFailedTests(t *testing.T) {
	Convey("cache failed tests", t, func() {
		c := gaetesting.TestingContext()
		fileContents := map[string]string{}
		oldGetFailed := getFailedTests

		failedTests := []string{}
		getFailedTests = func(c context.Context, b []byte) []string {
			return failedTests
		}

		Convey("no-op", func() {
			zr := makeZip(fileContents)
			So(cacheFailedTests(c, zr, "gspath"), ShouldBeNil)
		})

		fileContents["layout-test-results/full_results.json"] = "ignored"
		Convey("some failed tests", func() {
			failedTests = []string{"failed_test"}
			fileContents["failed_test"] = "test output"
			zr := makeZip(fileContents)

			So(cacheFailedTests(c, zr, "gspath"), ShouldBeNil)

			itm, err := memcache.GetKey(c, "gspath|failed_test")
			So(err, ShouldBeNil)
			So(itm.Value(), ShouldResemble, []byte("test output"))
		})

		getFailedTests = oldGetFailed
	})

}
