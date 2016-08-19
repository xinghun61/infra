package frontend

import (
	"bytes"
	"encoding/json"
	"infra/appengine/test-results/model"
	"net/http"
	"net/http/httptest"
	"testing"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/server/router"
	. "github.com/smartystreets/goconvey/convey"
)

func TestDeleteKeysHandler(t *testing.T) {
	t.Parallel()

	Convey("deleteKeysHandler", t, func() {
		ctx := memory.Use(context.Background())
		ds := datastore.Get(ctx)

		dataEntries := []model.DataEntry{
			{Data: []byte("foo"), ID: 1},
			{Data: []byte("bar"), ID: 2},
			{Data: []byte("baz"), ID: 3},
			{Data: []byte("qux"), ID: 4},
		}
		for _, de := range dataEntries {
			So(ds.Put(&de), ShouldBeNil)
		}
		dataKeys := make([]*datastore.Key, len(dataEntries))
		for i, de := range dataEntries {
			dataKeys[i] = ds.KeyForObj(&de)
		}

		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			ds.Testable().CatchupIndexes()
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

			res, err := ds.Exists(dataKeys[:2])
			So(err, ShouldBeNil)
			So(!res.Any(), ShouldBeTrue)
			res, err = ds.Exists(dataKeys[2:])
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
