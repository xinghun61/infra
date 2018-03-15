package handler

import (
	"crypto/sha1"
	"fmt"
	"io/ioutil"
	"net/http/httptest"
	"testing"
	"time"

	"infra/appengine/sheriff-o-matic/som/model"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

func TestAnnotationTreeWorker(t *testing.T) {
	Convey("run annotation migration", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestRecentTimeUTC)
		c = clock.Set(c, cl)

		alertIdx := datastore.IndexDefinition{
			Kind:     "AlertJSON",
			Ancestor: true,
			SortBy: []datastore.IndexColumn{
				{
					Property: "Resolved",
				},
				{
					Property:   "Date",
					Descending: false,
				},
			},
		}
		indexes := []*datastore.IndexDefinition{&alertIdx}
		datastore.GetTestable(c).AddIndexes(indexes...)

		w := httptest.NewRecorder()

		ctx := &router.Context{
			Context: c,
			Writer:  w,
		}

		ann := &model.Annotation{
			KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("test"))),
			Key:              "test",
			ModificationTime: datastore.RoundTime(clock.Now(c).Add(4 * time.Hour)),
		}

		So(datastore.Put(c, ann), ShouldBeNil)
		datastore.GetTestable(c).CatchupIndexes()

		alertJSON := &model.AlertJSON{
			ID:       "test",
			Tree:     datastore.MakeKey(c, "Tree", "test"),
			Resolved: false,
		}

		So(datastore.Put(c, alertJSON), ShouldBeNil)
		datastore.GetTestable(c).CatchupIndexes()

		AnnotationTreeWorker(ctx)

		r, err := ioutil.ReadAll(w.Body)
		So(err, ShouldBeNil)
		body := string(r)

		So(w.Code, ShouldEqual, 200)
		So(body, ShouldEqual, `[{"Tree":"agdkZXZ-YXBwcg4LEgRUcmVlIgR0ZXN0DA","KeyDigest":"a94a8fe5ccb19ba61c4c0873d391e987982fbbd3","key":"test","bugs":null,"comments":null,"snoozeTime":0,"group_id":"","ModificationTime":"2016-02-03T08:05:06Z"}]`)
	})
}
