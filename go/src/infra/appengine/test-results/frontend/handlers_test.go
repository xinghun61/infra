package frontend

import (
	"bytes"
	"encoding/json"
	"infra/appengine/test-results/model"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/server/router"
)

func TestDeleteKeysHandler(t *testing.T) {
	t.Parallel()

	Convey("deleteKeysHandler", t, func() {
		ctx := memory.Use(context.Background())

		dataEntries := []model.DataEntry{
			{Data: []byte("foo"), ID: 1},
			{Data: []byte("bar"), ID: 2},
			{Data: []byte("baz"), ID: 3},
			{Data: []byte("qux"), ID: 4},
		}
		for _, de := range dataEntries {
			So(datastore.Put(ctx, &de), ShouldBeNil)
		}
		dataKeys := make([]*datastore.Key, len(dataEntries))
		for i, de := range dataEntries {
			dataKeys[i] = datastore.KeyForObj(ctx, &de)
		}

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			datastore.GetTestable(ctx).CatchupIndexes()
			next(c)
		}

		r := router.New()
		r.POST(deleteKeysPath, router.NewMiddlewareChain(withTestingContext), deleteKeysHandler)
		srv := httptest.NewServer(r)
		client := &http.Client{}

		Convey("valid JSON body: deletes DataEntrys", func() {
			var encoded []string
			for _, dk := range dataKeys[:2] {
				encoded = append(encoded, dk.Encode())
			}
			buf := bytes.Buffer{}
			So(json.NewEncoder(&buf).Encode(struct {
				Keys []string `json:"keys"`
			}{encoded}), ShouldBeNil)

			resp, err := client.Post(srv.URL+deleteKeysPath, "application/json", &buf)
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, http.StatusOK)

			res, err := datastore.Exists(ctx, dataKeys[:2])
			So(err, ShouldBeNil)
			So(!res.Any(), ShouldBeTrue)
			res, err = datastore.Exists(ctx, dataKeys[2:])
			So(err, ShouldBeNil)
			So(res.All(), ShouldBeTrue)
		})

		Convey("invalid JSON: returns HTTP 200", func() {
			resp, err := client.Post(srv.URL+deleteKeysPath, "application/json", bytes.NewReader([]byte(`[`)))
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, http.StatusOK)
		})

		Convey("invalid key: returns HTTP 500", func() {
			buf := bytes.Buffer{}
			So(json.NewEncoder(&buf).Encode(struct {
				Keys []string `json:"keys"`
			}{
				[]string{"deadbeef"},
			}), ShouldBeNil)

			resp, err := client.Post(srv.URL+deleteKeysPath, "application/json", &buf)
			So(err, ShouldBeNil)
			So(resp.StatusCode, ShouldEqual, http.StatusInternalServerError)
		})
	})
}
