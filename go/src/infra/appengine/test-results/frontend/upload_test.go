package frontend

import (
	"bytes"
	"io"
	"io/ioutil"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"
	. "github.com/smartystreets/goconvey/convey"
)

func withTestingContext(c *router.Context, next router.Handler) {
	ctx := memory.Use(context.Background())
	ds := datastore.Get(ctx)
	testFileIdx, err := datastore.FindAndParseIndexYAML(filepath.Join("..", "model", "testdata"))
	if err != nil {
		panic(err)
	}
	ds.Testable().AddIndexes(testFileIdx...)
	ds.Testable().CatchupIndexes()

	c.Context = ctx
	next(c)
}

func TestUpload(t *testing.T) {
	t.Parallel()

	r := router.New()
	mw := router.NewMiddlewareChain(withTestingContext)
	r.POST("/testfile/upload", mw.Extend(withParsedUploadForm), uploadHandler)
	srv := httptest.NewServer(r)
	client := &http.Client{}

	Convey("upload", t, func() {
		Convey("no matching aggregate file in datastore", func() {
			var buf bytes.Buffer
			multi := multipart.NewWriter(&buf)
			// Form files.
			f, err := os.Open(filepath.Join("testdata", "full_results_0.json"))
			So(err, ShouldBeNil)
			defer f.Close()
			multiFile, err := multi.CreateFormFile("file", "full_results.json")
			So(err, ShouldBeNil)
			_, err = io.Copy(multiFile, f)
			So(err, ShouldBeNil)
			// Form fields.
			fields := []struct {
				key, val string
			}{
				{"master", "chromium.chromiumos"},
				{"builder", "test-builder"},
				{"test_type", "test-type"},
			}
			for _, field := range fields {
				f, err := multi.CreateFormField(field.key)
				So(err, ShouldBeNil)
				_, err = f.Write([]byte(field.val))
				So(err, ShouldBeNil)
			}
			multi.Close()

			req, err := http.NewRequest("POST", srv.URL+"/testfile/upload", &buf)
			So(err, ShouldBeNil)
			req.Header.Set("Content-Type", multi.FormDataContentType())
			resp, err := client.Do(req)
			So(err, ShouldBeNil)
			defer resp.Body.Close()
			So(resp.StatusCode, ShouldEqual, http.StatusOK)

			b, err := ioutil.ReadAll(resp.Body)
			So(err, ShouldBeNil)
			So(string(b), ShouldEqual, "OK")
		})
	})
}
