package client

import (
	"encoding/json"
	"fmt"
	"net/url"
	"testing"

	clientTest "infra/appengine/sheriff-o-matic/som/client/test"
	"infra/monitoring/messages"

	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/gae/service/memcache"

	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func urlParse(s string, t *testing.T) *url.URL {
	p, err := url.Parse(s)
	if err != nil {
		t.Errorf("failed to parse %s: %s", s, err)
	}
	return p
}

func TestMemcacheReader(t *testing.T) {
	Convey("MemcacheReader", t, func() {
		mr := &clientTest.MockReader{
			BuildValue: &messages.Build{
				Master:   "fake.master",
				Finished: true,
			},
		}
		ml := &messages.MasterLocation{
			URL: *urlParse("https://build.chromium.org/p/fake.master", t),
		}
		r := NewMemcacheReader(mr)
		ctx := memory.Use(context.Background())
		key := "fake.master/fake.builder/123"

		Convey("no cache", func() {
			Convey("rpc ok", func() {
				res, err := r.Build(ctx, ml, "fake.builder", 123)
				So(err, ShouldBeNil)
				So(res, ShouldResemble, mr.BuildValue)

				itm, err := memcache.GetKey(ctx, key)
				So(err, ShouldBeNil)

				dec := &messages.Build{}
				So(json.Unmarshal(itm.Value(), dec), ShouldBeNil)
				So(dec, ShouldResemble, mr.BuildValue)
			})

			Convey("rpc err", func() {
				mr.BuildFetchError = fmt.Errorf("fetch error")

				_, err := r.Build(ctx, ml, "fake.builder", 123)
				So(err, ShouldResemble, mr.BuildFetchError)
			})

			Convey("rpc ok, don't cache unfinished builds", func() {
				mr.BuildValue.Finished = false

				res, err := r.Build(ctx, ml, "fake.builder", 123)
				So(err, ShouldBeNil)
				So(res, ShouldResemble, mr.BuildValue)

				_, err = memcache.GetKey(ctx, key)
				So(err, ShouldResemble, memcache.ErrCacheMiss)
			})
		})

		Convey("when cached, no rpc", func() {
			itm := memcache.NewItem(ctx, key)

			data, err := json.Marshal(mr.BuildValue)
			So(err, ShouldBeNil)
			itm.SetValue(data)
			So(memcache.Set(ctx, itm), ShouldBeNil)

			oldVal := mr.BuildValue
			mr.BuildValue = &messages.Build{
				Master: "other.master",
			}

			res, err := r.Build(ctx, ml, "fake.builder", 123)
			So(err, ShouldBeNil)
			So(res, ShouldResemble, oldVal)

			itm, err = memcache.GetKey(ctx, key)
			So(err, ShouldBeNil)

			dec := &messages.Build{}
			So(json.Unmarshal(itm.Value(), dec), ShouldBeNil)
			So(dec, ShouldResemble, oldVal)
		})
	})
}
