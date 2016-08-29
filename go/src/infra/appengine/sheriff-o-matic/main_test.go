// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"crypto/sha1"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/julienschmidt/httprouter"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

var _ = fmt.Printf

func TestMain(t *testing.T) {
	t.Parallel()

	Convey("main", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestTimeUTC)
		c = clock.Set(c, cl)

		ds := datastore.Get(c)
		w := httptest.NewRecorder()

		Convey("index", func() {
			c = auth.SetAuthenticator(c, []auth.Method(nil))

			Convey("anonymous", func() {
				indexPage(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "chromium"),
				})

				r, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				body := string(r)
				So(w.Code, ShouldEqual, 500)
				So(body, ShouldNotContainSubstring, "som-app")
				So(body, ShouldContainSubstring, "login")
			})

			c = auth.SetAuthenticator(c, []auth.Method{authtest.FakeAuth{
				User: &auth.User{
					Identity: "user:user@example.com",
				},
			}})
			authState := &authtest.FakeState{
				Identity: "user:user@example.com",
			}
			c = auth.WithState(c, authState)

			Convey("No access", func() {
				indexPage(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "chromium"),
				})

				So(w.Code, ShouldEqual, 200)
				r, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				body := string(r)
				So(body, ShouldNotContainSubstring, "som-app")
				So(body, ShouldContainSubstring, "Access denied")
			})
			authState.IdentityGroups = []string{authGroup}

			Convey("good path", func() {
				indexPage(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", "chromium"),
				})
				r, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				body := string(r)
				So(body, ShouldContainSubstring, "som-app")
				So(w.Code, ShouldEqual, 200)
			})
		})

		Convey("/api/v1", func() {
			alertsIdx := datastore.IndexDefinition{
				Kind:     "AlertsJSON",
				Ancestor: true,
				SortBy: []datastore.IndexColumn{
					{
						Property:   "Date",
						Descending: true,
					},
				},
			}
			ds.Testable().AddIndexes(&alertsIdx)

			isGoogler := true
			requireGoogler = func(w http.ResponseWriter, c context.Context) bool {
				return isGoogler
			}

			Convey("/trees", func() {
				Convey("no trees yet", func() {
					getTreesHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
					})

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "[]")
				})

				tree := &Tree{
					Name:        "oak",
					DisplayName: "Oak",
				}
				So(ds.Put(tree), ShouldBeNil)
				ds.Testable().CatchupIndexes()

				Convey("basic tree", func() {
					getTreesHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
					})

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, `[{"name":"oak","display_name":"Oak"}]`)
				})
			})

			Convey("/alerts", func() {
				alerts := &AlertsJSON{
					Tree:     ds.MakeKey("Tree", "oak"),
					Contents: []byte("hithere"),
				}
				Convey("GET", func() {
					Convey("no alerts yet", func() {
						getAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "oak"),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 404)
						So(body, ShouldContainSubstring, "Tree")
					})

					So(ds.Put(alerts), ShouldBeNil)

					Convey("basic alerts", func() {
						getAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "oak"),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 200)
						So(body, ShouldEqual, "hithere")
					})
				})

				Convey("POST", func() {
					q := datastore.NewQuery("AlertsJSON")
					results := []*AlertsJSON{}
					So(ds.GetAll(q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					postAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"thing":"FOOBAR"}`),
						Params:  makeParams("tree", "oak"),
					})

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					ds.Testable().CatchupIndexes()
					results = []*AlertsJSON{}
					So(ds.GetAll(q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.Tree, ShouldResemble, alerts.Tree)
					So(string(itm.Contents), ShouldEqual, `{"date":"0001-02-03 04:05:06.000000007 +0000 UTC","thing":"FOOBAR"}`)
				})
			})

			Convey("/annotations", func() {
				Convey("GET", func() {
					Convey("no annotations yet", func() {
						getAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 200)
						So(body, ShouldEqual, "[]")
					})

					ann := &Annotation{
						KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
						Key:              "foobar",
						Bugs:             []string{"hi", "bugz"},
						SnoozeTime:       123123,
						ModificationTime: clock.Now(c).Add(4 * time.Hour),
					}
					So(ds.Put(ann), ShouldBeNil)
					ds.Testable().CatchupIndexes()

					Convey("basic annotation", func() {
						getAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 200)
						So(body, ShouldEqual, `[{"KeyDigest":"8843d7f92416211de9ebb963ff4ce28125932878","key":"foobar","bugs":["hi","bugz"],"snoozeTime":123123,"ModificationTime":"0001-02-03T08:05:06Z"}]`)
					})
				})
				Convey("POST", func() {
					Convey("invalid action", func() {
						postAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest(""),
							Params:  makeParams("annKey", "foobar", "action", "lolwut"),
						})

						So(w.Code, ShouldEqual, 404)
					})
					ann := &Annotation{
						Key:              "foobar",
						KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
						ModificationTime: cl.Now(),
					}
					cl.Add(time.Hour)

					Convey("add", func() {
						change := `{"snoozeTime":123123}`
						postAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest(change),
							Params:  makeParams("annKey", "foobar", "action", "add"),
						})

						So(w.Code, ShouldEqual, 200)

						So(ds.Get(ann), ShouldBeNil)
						So(ann.SnoozeTime, ShouldEqual, 123123)

						Convey("bad change", func() {
							w = httptest.NewRecorder()
							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(`{"bugs":["oooops"]}`),
								Params:  makeParams("annKey", "foobar", "action", "add"),
							})

							So(w.Code, ShouldEqual, 400)

							So(ds.Get(ann), ShouldBeNil)
							So(ann.SnoozeTime, ShouldEqual, 123123)
							So(ann.Bugs, ShouldBeNil)
						})
					})

					Convey("remove", func() {
						Convey("can't remove non-existant annotation", func() {
							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(""),
								Params:  makeParams("annKey", "foobar", "action", "remove"),
							})

							So(w.Code, ShouldEqual, 404)
						})

						ann.SnoozeTime = 123
						So(ds.Put(ann), ShouldBeNil)

						Convey("basic", func() {
							So(ann.SnoozeTime, ShouldEqual, 123)

							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(`{"snoozeTime":true}`),
								Params:  makeParams("annKey", "foobar", "action", "remove"),
							})

							So(w.Code, ShouldEqual, 200)
							So(ds.Get(ann), ShouldBeNil)
							So(ann.SnoozeTime, ShouldEqual, 0)
						})

					})
				})
			})

			Convey("/bugqueue", func() {
				// Bug queue is weird to test because it relies on network requests.
				Convey("get bug queue handler", func() {
					getBugQueueHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
					})

					_, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 500)
				})

				Convey("refresh bug queue handler", func() {
					refreshBugQueueHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
					})

					_, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 500)
				})

				Convey("refresh bug queue", func() {
					_, err := refreshBugQueue(c, "tree")
					So(err, ShouldNotBeNil)
				})
			})
		})
	})
}

func makeGetRequest() *http.Request {
	req, _ := http.NewRequest("GET", "/doesntmatter", nil)
	return req
}

func makePostRequest(body string) *http.Request {
	req, _ := http.NewRequest("POST", "/doesntmatter", strings.NewReader(body))
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

func TestWriteSettings(t *testing.T) {
	t.Parallel()

	Convey("write settings", t, func() {
		c := gaetesting.TestingContext()
		ds := datastore.Get(c)

		Convey("writeTrees", func() {
			Convey("basic", func() {
				err := writeTrees(c, "foo")
				So(err, ShouldBeNil)

				t := &Tree{
					Name: "foo",
				}
				So(ds.Get(t), ShouldBeNil)
				So(t.DisplayName, ShouldEqual, "Foo")
			})

			tree := &Tree{
				Name:        "oak",
				DisplayName: "Oaakk",
			}

			So(ds.Put(tree), ShouldBeNil)
			ds.Testable().CatchupIndexes()

			Convey("overwrite tree", func() {
				err := writeTrees(c, "oak")
				So(err, ShouldBeNil)

				So(ds.Get(tree), ShouldBeNil)
				So(tree.DisplayName, ShouldEqual, "Oak")
			})

			Convey("overwrite tree with new display name", func() {
				err := writeTrees(c, "oak:Oaakk")
				So(err, ShouldBeNil)

				So(ds.Get(tree), ShouldBeNil)
				So(tree.DisplayName, ShouldEqual, "Oaakk")
			})
		})

		Convey("writeAlertStreams", func() {
			tree := &Tree{
				Name:        "oak",
				DisplayName: "Oak",
			}

			So(ds.Put(tree), ShouldBeNil)
			ds.Testable().CatchupIndexes()

			Convey("basic", func() {
				err := writeAlertStreams(c, "oak:thing")
				So(err, ShouldBeNil)

				So(ds.Get(tree), ShouldBeNil)
				So(tree.DisplayName, ShouldEqual, "Oak")
				So(tree.AlertStreams, ShouldResemble, []string{"thing"})
			})

		})

		Convey("writeBugQueueLabels", func() {
			tree := &Tree{
				Name:          "oak",
				DisplayName:   "Oak",
				BugQueueLabel: "test",
			}

			So(ds.Put(tree), ShouldBeNil)
			ds.Testable().CatchupIndexes()

			Convey("basic", func() {
				err := writeBugQueueLabels(c, "oak:thing")
				So(err, ShouldBeNil)

				So(ds.Get(tree), ShouldBeNil)
				So(tree.Name, ShouldEqual, "oak")
				So(tree.DisplayName, ShouldEqual, "Oak")
				So(tree.BugQueueLabel, ShouldEqual, "thing")
			})

			Convey("remove label", func() {
				err := writeBugQueueLabels(c, "oak:")
				So(err, ShouldBeNil)

				So(ds.Get(tree), ShouldBeNil)
				So(tree.Name, ShouldEqual, "oak")
				So(tree.DisplayName, ShouldEqual, "Oak")
				So(tree.BugQueueLabel, ShouldEqual, "")
			})
		})
	})
}

func TestRevRangeHandler(t *testing.T) {
	t.Parallel()

	Convey("get rev range", t, func() {
		Convey("ok", func() {
			c := gaetesting.TestingContext()
			c = authtest.MockAuthConfig(c)
			w := httptest.NewRecorder()

			getRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("start", "123", "end", "456"),
			})

			So(w.Code, ShouldEqual, 301)
		})
		Convey("bad request", func() {
			c := gaetesting.TestingContext()
			c = authtest.MockAuthConfig(c)
			w := httptest.NewRecorder()

			getRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
			})

			So(w.Code, ShouldEqual, 400)
		})
	})
}
