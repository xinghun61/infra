// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"crypto/sha1"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

var _ = fmt.Printf

func TestAnnotation(t *testing.T) {
	t.Parallel()

	Convey("Annotation", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestTimeUTC)
		c = clock.Set(c, cl)
		ds := datastore.Get(c)

		ann := &Annotation{
			Key:              "foobar",
			KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
			ModificationTime: cl.Now(),
		}
		cl.Add(time.Hour)

		Convey("allows weird keys", func() {
			ann.Key = "hihih\"///////%20     lol"
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(ds.Put(ann), ShouldBeNil)
		})

		Convey("allows long keys", func() {
			// App engine key size limit is 500 characters
			ann.Key = strings.Repeat("annnn", 200)
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(ds.Put(ann), ShouldBeNil)
		})

		Convey("validBug", func() {
			Convey("number", func() {
				res, err := validBug("123123")
				So(err, ShouldBeNil)
				So(res, ShouldEqual, "https://crbug.com/123123")
			})

			Convey("bugs.chromium.org", func() {
				res, err := validBug("bugs.chromium.org/aasasnans")
				So(err, ShouldBeNil)
				So(res, ShouldEqual, "https://bugs.chromium.org/aasasnans")
			})

			Convey("crbug.com", func() {
				res, err := validBug("crbug.com/123123")
				So(err, ShouldBeNil)
				So(res, ShouldEqual, "https://crbug.com/123123")
			})

			Convey("invalid", func() {
				_, err := validBug("lolwat")
				So(err, ShouldNotBeNil)
			})

		})

		Convey("with mocked ValidBug", func() {
			Convey("add", func() {
				Convey("time", func() {
					changeS := `{"snoozeTime":123123}`
					err := ann.add(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(ann.SnoozeTime, ShouldEqual, 123123)
					So(ann.Bugs, ShouldBeNil)
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":["123123"]}`
					Convey("basic", func() {
						err := ann.add(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldResemble, []string{"https://crbug.com/123123"})
						So(ann.ModificationTime, ShouldResemble, cl.Now())

						Convey("duplicate bugs", func() {
							cl.Add(time.Hour)
							err = ann.add(c, strings.NewReader(changeString))
							So(err, ShouldBeNil)

							So(ann.SnoozeTime, ShouldEqual, 0)
							So(ann.Bugs, ShouldResemble, []string{"https://crbug.com/123123"})
							So(ann.ModificationTime, ShouldResemble, cl.Now())
						})
					})

					Convey("bug error", func() {
						err := ann.add(c, strings.NewReader("hi"))

						So(err, ShouldNotBeNil)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})
			})

			Convey("remove", func() {
				ann.SnoozeTime = 100
				ann.Bugs = []string{"https://crbug.com/123123", "bug2"}

				Convey("time", func() {
					changeS := `{"snoozeTime":true}`
					err := ann.remove(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(ann.SnoozeTime, ShouldEqual, 0)
					So(ann.Bugs, ShouldResemble, []string{"https://crbug.com/123123", "bug2"})
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":["123123"]}`
					Convey("basic", func() {
						err := ann.remove(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"bug2"})
						So(ann.ModificationTime, ShouldResemble, cl.Now())
					})

					Convey("bug error", func() {
						err := ann.remove(c, strings.NewReader("badbugzman"))

						So(err, ShouldNotBeNil)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"https://crbug.com/123123", "bug2"})
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

			})
		})
	})
}
