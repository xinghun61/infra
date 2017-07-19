// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"infra/appengine/test-results/model"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/taskqueue"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func createTestFile(
	ctx context.Context, name string, lastMod time.Time, data []string) {
	var dataKeys []*datastore.Key
	for _, datum := range data {
		de := model.DataEntry{Data: []byte(datum)}
		So(datastore.Put(ctx, &de), ShouldBeNil)
		dataKeys = append(dataKeys, datastore.KeyForObj(ctx, &de))
	}
	So(datastore.Put(ctx, &model.TestFile{
		Name:     name,
		LastMod:  lastMod,
		DataKeys: dataKeys,
	}), ShouldBeNil)
}

func TestDeleteOldResults(t *testing.T) {
	t.Parallel()

	Convey("deleteOldResultsHandler", t, func() {
		// Prepare context.
		ctx := memory.Use(context.Background())
		ctx, cancelFunc := context.WithTimeout(ctx, 10*time.Minute)
		defer cancelFunc()

		// Put 900 old files into datastore. The number of TestFile and DataEntry is picked to make
		// sure that code limiting number of entities deleted at once to 500 is
		// triggered.
		year := time.Hour * 24 * 400
		for i := 0; i < 300; i++ {
			createTestFile(
				ctx, "full_results.json", clock.Get(ctx).Now().Add(-2*year).UTC(),
				[]string{"a", "b", "c"})
			createTestFile(
				ctx, "full_results.json", clock.Get(ctx).Now().Add(-2*year).UTC(),
				[]string{"d"})
			createTestFile(
				ctx, "results.json", clock.Get(ctx).Now().Add(-2*year).UTC(),
				[]string{})
		}

		// Put another entity with a fake key that points to a non-existant
		// DataEntry entity to test that we do not fail in this case.
		So(datastore.Put(ctx, &model.TestFile{
			Name:    "results.json",
			LastMod: clock.Get(ctx).Now().Add(-2 * year).UTC(),
			DataKeys: []*datastore.Key{
				datastore.NewKey(ctx, "DataEntry", "foo", 42, nil),
			},
		}), ShouldBeNil)

		// Create one entity that is recent and should not be deleted.
		createTestFile(
			ctx, "results-small.json",
			clock.Get(ctx).Now().Add(-time.Hour*200*24).UTC(), []string{"foo"})

		// Disable datastore inconsistency to avoid tests flakiness.
		withTestingContext := func(c *router.Context, next router.Handler) {
			c.Context = ctx
			datastore.GetTestable(ctx).Consistent(true)
			datastore.GetTestable(ctx).AutoIndex(true)
			datastore.GetTestable(ctx).CatchupIndexes()
			taskqueue.GetTestable(ctx).CreateQueue(deleteKeysQueueName)
			next(c)
		}

		// Set up router and init test server with it.
		r := router.New()
		r.GET(
			"/internal/cron/delete_old_results",
			router.NewMiddlewareChain(withTestingContext),
			deleteOldResultsHandler)
		srv := httptest.NewServer(r)

		// Send request.
		client := &http.Client{}
		resp, err := client.Get(srv.URL + "/internal/cron/delete_old_results")
		So(err, ShouldBeNil)
		defer resp.Body.Close()

		// Verify that old files were deleted.
		datastore.GetTestable(ctx).CatchupIndexes()
		q := datastore.NewQuery("TestFile")
		var remainingFiles []*model.TestFile
		So(datastore.GetAll(ctx, q, &remainingFiles), ShouldBeNil)
		So(len(remainingFiles), ShouldEqual, 1)
		So(remainingFiles[0].Name, ShouldEqual, "results-small.json")

		// Verify that old data entities were deleted.
		q = datastore.NewQuery("DataEntry")
		var remainingDataEntries []*model.DataEntry
		So(datastore.GetAll(ctx, q, &remainingDataEntries), ShouldBeNil)
		So(len(remainingDataEntries), ShouldEqual, 1)
		So(string(remainingDataEntries[0].Data), ShouldEqual, "foo")
	})
}
