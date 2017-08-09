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

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/gaetesting"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	. "github.com/smartystreets/goconvey/convey"
)

var _ = fmt.Printf

func TestAnnotation(t *testing.T) {
	t.Parallel()

	Convey("Annotation", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestTimeUTC)
		c = clock.Set(c, cl)

		ann := &Annotation{
			Key:              "foobar",
			KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
			ModificationTime: cl.Now(),
		}
		cl.Add(time.Hour)

		Convey("allows weird keys", func() {
			ann.Key = "hihih\"///////%20     lol"
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(datastore.Put(c, ann), ShouldBeNil)
		})

		Convey("allows long keys", func() {
			// App engine key size limit is 500 characters
			ann.Key = strings.Repeat("annnn", 200)
			ann.KeyDigest = fmt.Sprintf("%x", sha1.Sum([]byte(ann.Key)))
			So(datastore.Put(c, ann), ShouldBeNil)
		})

		Convey("validBug", func() {
			Convey("number", func() {
				res, err := validBug("123123")
				So(err, ShouldBeNil)
				So(res, ShouldEqual, "123123")
			})

			Convey("bugs.chromium.org", func() {
				_, err := validBug("bugs.chromium.org/aasasnans")
				So(err, ShouldNotBeNil)
			})

			Convey("crbug.com", func() {
				res, err := validBug("crbug.com/123123")
				So(err, ShouldBeNil)
				So(res, ShouldEqual, "123123")
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
					needRefresh, err := ann.add(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(needRefresh, ShouldBeFalse)
					So(ann.SnoozeTime, ShouldEqual, 123123)
					So(ann.Bugs, ShouldBeNil)
					So(ann.Comments, ShouldBeNil)
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":["123123"]}`
					Convey("basic", func() {
						needRefresh, err := ann.add(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeTrue)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldResemble, []string{"123123"})
						So(ann.ModificationTime, ShouldResemble, cl.Now())

						Convey("duplicate bugs", func() {
							cl.Add(time.Hour)
							needRefresh, err = ann.add(c, strings.NewReader(changeString))
							So(err, ShouldBeNil)
							So(needRefresh, ShouldBeFalse)

							So(ann.SnoozeTime, ShouldEqual, 0)
							So(ann.Bugs, ShouldResemble, []string{"123123"})
							So(ann.Comments, ShouldBeNil)
							// We aren't changing the annotation, so the modification time shouldn't update.
							So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
						})
					})

					Convey("bug error", func() {
						needRefresh, err := ann.add(c, strings.NewReader("hi"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)
						So(ann.Comments, ShouldBeNil)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

				Convey("comments", func() {
					changeString := `{"comments":["woah", "man", "comments"]}`
					Convey("basic", func() {
						needRefresh, err := ann.add(c, strings.NewReader(changeString))
						t := cl.Now()

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)

						So(ann.Comments, ShouldResemble, []Comment{{"woah", "", t}, {"man", "", t}, {"comments", "", t}})
						So(ann.ModificationTime, ShouldResemble, t)
					})

					Convey("comments error", func() {
						needRefresh, err := ann.add(c, strings.NewReader("plz don't add me"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 0)
						So(ann.Bugs, ShouldBeNil)
						So(ann.Comments, ShouldBeNil)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})
			})

			Convey("remove", func() {
				t := cl.Now()
				comments := []Comment{{"hello", "", t}, {"world", "", t}, {"hehe", "", t}}
				ann.SnoozeTime = 100
				ann.Bugs = []string{"123123", "bug2"}
				ann.Comments = comments

				Convey("time", func() {
					changeS := `{"snoozeTime":true}`
					needRefresh, err := ann.remove(c, strings.NewReader(changeS))

					So(err, ShouldBeNil)
					So(needRefresh, ShouldBeFalse)
					So(ann.SnoozeTime, ShouldEqual, 0)
					So(ann.Bugs, ShouldResemble, []string{"123123", "bug2"})
					So(ann.Comments, ShouldResemble, comments)
					So(ann.ModificationTime, ShouldResemble, cl.Now())
				})

				Convey("bugs", func() {
					changeString := `{"bugs":["123123"]}`
					Convey("basic", func() {
						needRefresh, err := ann.remove(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Comments, ShouldResemble, comments)
						So(ann.Bugs, ShouldResemble, []string{"bug2"})
						So(ann.ModificationTime, ShouldResemble, cl.Now())
					})

					Convey("bug error", func() {
						needRefresh, err := ann.remove(c, strings.NewReader("badbugzman"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"123123", "bug2"})
						So(ann.Comments, ShouldResemble, comments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

				Convey("comments", func() {
					Convey("basic", func() {
						changeString := `{"comments":[1]}`
						needRefresh, err := ann.remove(c, strings.NewReader(changeString))

						So(err, ShouldBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"123123", "bug2"})
						So(ann.Comments, ShouldResemble, []Comment{{"hello", "", t}, {"hehe", "", t}})
						So(ann.ModificationTime, ShouldResemble, cl.Now())
					})

					Convey("bad format", func() {
						needRefresh, err := ann.remove(c, strings.NewReader("don't do this"))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"123123", "bug2"})
						So(ann.Comments, ShouldResemble, comments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})

					Convey("invalid index", func() {
						changeString := `{"comments":[3]}`
						needRefresh, err := ann.remove(c, strings.NewReader(changeString))

						So(err, ShouldNotBeNil)
						So(needRefresh, ShouldBeFalse)
						So(ann.SnoozeTime, ShouldEqual, 100)
						So(ann.Bugs, ShouldResemble, []string{"123123", "bug2"})
						So(ann.Comments, ShouldResemble, comments)
						So(ann.ModificationTime, ShouldResemble, cl.Now().Add(-time.Hour))
					})
				})

			})
		})
	})
}
