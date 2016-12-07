// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package som

import (
	"bytes"
	"crypto/sha1"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/auth/authtest"
	"github.com/luci/luci-go/server/auth/xsrf"
	"github.com/luci/luci-go/server/router"

	. "github.com/smartystreets/goconvey/convey"
)

var _ = fmt.Printf

func TestMain(t *testing.T) {
	t.Parallel()

	Convey("main", t, func() {
		c := gaetesting.TestingContext()
		cl := testclock.New(testclock.TestRecentTimeUTC)
		c = clock.Set(c, cl)

		w := httptest.NewRecorder()

		tok, err := xsrf.Token(c)
		So(err, ShouldBeNil)

		Convey("index", func() {
			c = auth.SetAuthenticator(c, []auth.Method(nil))

			Convey("pathless", func() {
				indexPage(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("path", ""),
				})

				So(w.Code, ShouldEqual, 302)
			})

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
			datastore.GetTestable(c).AddIndexes(&alertsIdx)

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
				So(datastore.Put(c, tree), ShouldBeNil)
				datastore.GetTestable(c).CatchupIndexes()

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
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
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

					So(datastore.Put(c, alerts), ShouldBeNil)

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

					Convey("trooper alerts", func() {
						ta := datastore.GetTestable(c)

						datastore.Put(c, &Tree{
							Name: "chromium",
						})
						datastore.Put(c, &AlertsJSON{
							ID:       1,
							Tree:     datastore.MakeKey(c, "Tree", "chromium"),
							Contents: []byte("{}"),
						})
						ta.CatchupIndexes()

						getAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "trooper"),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 200)
						So(body, ShouldEqual, `{"alerts":[],"date":"0001-01-01T00:00:00Z","revision_summaries":null,"swarming":{"dead":null,"quarantined":null,"errors":["auth: the library is not properly configured"]},"timestamp":0}`)
					})

					Convey("getSwarmingAlerts", func() {
						// HACK:
						oldOAClient := getOAuthClient
						getOAuthClient = func(c context.Context) (*http.Client, error) {
							return &http.Client{}, nil
						}

						sa := getSwarmingAlerts(c)

						getOAuthClient = oldOAClient
						So(sa, ShouldResemble, &swarmingAlerts{
							Error: []string{"googleapi: Error 403: , forbidden", "googleapi: Error 403: , forbidden"},
						})
					})
				})

				Convey("POST", func() {
					q := datastore.NewQuery("AlertsJSON")
					results := []*AlertsJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					postAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"timestamp": 12345.0}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertsJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.Tree, ShouldResemble, alerts.Tree)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt, ShouldResemble, map[string]interface{}{
						"date":      "2016-02-03 04:05:06.000000007 +0000 UTC",
						"timestamp": 12345.0,
					})
				})

				Convey("POST err", func() {
					q := datastore.NewQuery("AlertsJSON")
					results := []*AlertsJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					postAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`not valid json`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
				})

				Convey("POST err, valid but wrong json", func() {
					q := datastore.NewQuery("AlertsJSON")
					results := []*AlertsJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					postAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
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
						ModificationTime: datastore.RoundTime(clock.Now(c).Add(4 * time.Hour)),
					}
					So(datastore.Put(c, ann), ShouldBeNil)
					datastore.GetTestable(c).CatchupIndexes()

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
						rslt := []*Annotation{}
						So(json.NewDecoder(strings.NewReader(body)).Decode(&rslt), ShouldBeNil)
						So(rslt, ShouldHaveLength, 1)
						So(rslt[0], ShouldResemble, ann)
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

					Convey("invalid json", func() {
						postAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest("invalid json"),
							Params:  makeParams("annKey", "foobar", "action", "add"),
						})

						So(w.Code, ShouldEqual, http.StatusBadRequest)
					})

					ann := &Annotation{
						Key:              "foobar",
						KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
						ModificationTime: datastore.RoundTime(clock.Now(c)),
					}
					cl.Add(time.Hour)

					makeChange := func(data map[string]interface{}, tok string) string {
						change, err := json.Marshal(map[string]interface{}{
							"xsrf_token": tok,
							"data":       data,
						})
						So(err, ShouldBeNil)
						return string(change)
					}
					Convey("add, bad xsrf token", func() {
						postAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest(makeChange(map[string]interface{}{
								"snoozeTime": 123123,
							}, "no good token")),
							Params: makeParams("annKey", "foobar", "action", "add"),
						})

						So(w.Code, ShouldEqual, http.StatusForbidden)
					})

					Convey("add", func() {
						postAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest(makeChange(map[string]interface{}{
								"snoozeTime": 123123,
							}, tok)),
							Params: makeParams("annKey", "foobar", "action", "add"),
						})

						So(w.Code, ShouldEqual, 200)

						So(datastore.Get(c, ann), ShouldBeNil)
						So(ann.SnoozeTime, ShouldEqual, 123123)

						Convey("bad change", func() {
							w = httptest.NewRecorder()
							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(makeChange(map[string]interface{}{
									"bugs": []string{"ooooops"},
								}, tok)),
								Params: makeParams("annKey", "foobar", "action", "add"),
							})

							So(w.Code, ShouldEqual, 400)

							So(datastore.Get(c, ann), ShouldBeNil)
							So(ann.SnoozeTime, ShouldEqual, 123123)
							So(ann.Bugs, ShouldBeNil)
						})
					})

					Convey("remove", func() {
						Convey("can't remove non-existant annotation", func() {
							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(makeChange(nil, tok)),
								Params:  makeParams("annKey", "foobar", "action", "remove"),
							})

							So(w.Code, ShouldEqual, 404)
						})

						ann.SnoozeTime = 123
						So(datastore.Put(c, ann), ShouldBeNil)

						Convey("basic", func() {
							So(ann.SnoozeTime, ShouldEqual, 123)

							postAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(makeChange(map[string]interface{}{
									"snoozeTime": true,
								}, tok)),
								Params: makeParams("annKey", "foobar", "action", "remove"),
							})

							So(w.Code, ShouldEqual, 200)
							So(datastore.Get(c, ann), ShouldBeNil)
							So(ann.SnoozeTime, ShouldEqual, 0)
						})

					})
				})
			})

			Convey("/restarts", func() {
				c := gaetesting.TestingContext()
				w := httptest.NewRecorder()
				c = info.SetFactory(c, func(ic context.Context) info.RawInterface {
					return giMock{dummy.Info(), "", time.Now(), nil}
				})

				c = urlfetch.Set(c, &mockGitilesTransport{
					map[string]string{
						"https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/gatekeeper_trees.json?format=text": `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"],
            "https://build.chromium.org/p/chromium.android": [
              "Android N5X Swarm Builder"
            ],
            "https://build.chromium.org/p/chromium.chrome": ["*"],
            "https://build.chromium.org/p/chromium.chromiumos": ["*"],
            "https://build.chromium.org/p/chromium.gpu": ["*"],
            "https://build.chromium.org/p/chromium.infra.cron": ["*"],
            "https://build.chromium.org/p/chromium.linux": ["*"],
            "https://build.chromium.org/p/chromium.mac": ["*"],
            "https://build.chromium.org/p/chromium.memory": ["*"],
            "https://build.chromium.org/p/chromium.webkit": ["*"],
            "https://build.chromium.org/p/chromium.win": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
						"https://chrome-internal.googlesource.com/infradata/master-manager/+/master/desired_master_state.json?format=text": `
{
	"master_states":{
  	"master.chromium":[
	     {
	       "desired_state":"offline",
	       "transition_time_utc":"2015-11-19T16:47:00Z"
	     },
	     {
	       "desired_state":"running",
	       "transition_time_utc":"2016-11-19T02:30:00.0Z"
	     }
	  ]
	}
}`,
					},
				})

				getRestartingMastersHandler(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("tree", "chromium"),
				})

				_, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				So(w.Code, ShouldEqual, 200)

				w = httptest.NewRecorder()
				getRestartingMastersHandler(&router.Context{
					Context: c,
					Writer:  w,
					Request: makeGetRequest(),
					Params:  makeParams("tree", "non-existent"),
				})

				b, err := ioutil.ReadAll(w.Body)
				So(err, ShouldBeNil)
				So(w.Code, ShouldEqual, 404)
				So(string(b), ShouldEqual, "Unrecognized tree name")
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
					// HACK:
					oldOAClient := getOAuthClient
					getOAuthClient = func(c context.Context) (*http.Client, error) {
						return &http.Client{}, nil
					}

					_, err := refreshBugQueue(c, "label")
					So(err, ShouldNotBeNil)
					getOAuthClient = oldOAClient
				})

				Convey("get owned bugs", func() {
					getOwnedBugsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
						Params:  makeParams("label", "infra-troopers"),
					})

					_, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 200)
				})

				Convey("get alternate email", func() {
					e := getAlternateEmail("test@chromium.org")
					So(e, ShouldEqual, "test@google.com")

					e = getAlternateEmail("test@google.com")
					So(e, ShouldEqual, "test@chromium.org")
				})
			})
		})

		Convey("cron", func() {
			Convey("flushOldAnnotations", func() {
				getAllAnns := func() []*Annotation {
					anns := []*Annotation{}
					So(datastore.GetAll(c, datastore.NewQuery("Annotation"), &anns), ShouldBeNil)
					return anns
				}

				ann := &Annotation{
					KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
					Key:              "foobar",
					ModificationTime: datastore.RoundTime(cl.Now()),
				}
				So(datastore.Put(c, ann), ShouldBeNil)
				datastore.GetTestable(c).CatchupIndexes()

				Convey("current not deleted", func() {
					num, err := flushOldAnnotations(c)
					So(err, ShouldBeNil)
					So(num, ShouldEqual, 0)
					So(getAllAnns(), ShouldResemble, []*Annotation{ann})
				})

				ann.ModificationTime = cl.Now().Add(-(annotationExpiration + time.Hour))
				So(datastore.Put(c, ann), ShouldBeNil)
				datastore.GetTestable(c).CatchupIndexes()

				Convey("old deleted", func() {
					num, err := flushOldAnnotations(c)
					So(err, ShouldBeNil)
					So(num, ShouldEqual, 1)
					So(getAllAnns(), ShouldResemble, []*Annotation{})
				})

				datastore.GetTestable(c).CatchupIndexes()
				q := datastore.NewQuery("Annotation")
				anns := []*Annotation{}
				datastore.GetTestable(c).CatchupIndexes()
				datastore.GetAll(c, q, &anns)
				datastore.Delete(c, anns)
				anns = []*Annotation{
					{
						KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar2"))),
						Key:              "foobar2",
						ModificationTime: datastore.RoundTime(cl.Now()),
					},
					{
						KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
						Key:              "foobar",
						ModificationTime: datastore.RoundTime(cl.Now().Add(-(annotationExpiration + time.Hour))),
					},
				}
				So(datastore.Put(c, anns), ShouldBeNil)
				datastore.GetTestable(c).CatchupIndexes()

				Convey("only delete old", func() {
					num, err := flushOldAnnotations(c)
					So(err, ShouldBeNil)
					So(num, ShouldEqual, 1)
					So(getAllAnns(), ShouldResemble, anns[:1])
				})

				Convey("handler", func() {
					ctx := &router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(""),
						Params:  makeParams("annKey", "foobar", "action", "add"),
					}

					flushOldAnnotationsHandler(ctx)
				})
			})
		})

		Convey("clientmon", func() {
			c = auth.SetAuthenticator(c, []auth.Method(nil))
			body := &eCatcherReq{XSRFToken: tok}
			bodyBytes, err := json.Marshal(body)
			So(err, ShouldBeNil)
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makePostRequest(string(bodyBytes)),
				Params:  makeParams("xsrf_token", tok),
			}

			postClientMonHandler(ctx)
			So(w.Code, ShouldEqual, 200)
		})

		Convey("treelogo", func() {
			c = auth.SetAuthenticator(c, []auth.Method(nil))
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("tree", "chromium"),
			}

			getTreeLogo(ctx, "", &noopSigner{})
			So(w.Code, ShouldEqual, 302)
		})

		Convey("treelogo fail", func() {
			c = auth.SetAuthenticator(c, []auth.Method(nil))
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("tree", "chromium"),
			}

			getTreeLogo(ctx, "", &noopSigner{fmt.Errorf("fail")})
			So(w.Code, ShouldEqual, 500)
		})

		Convey("noop", func() {
			noopHandler(nil)
		})
	})
}

type noopSigner struct {
	err error
}

func (n *noopSigner) SignBytes(c context.Context, b []byte) (string, []byte, error) {
	return string(b), b, n.err
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
		Convey("bad oauth", func() {
			c := gaetesting.TestingContext()
			c = authtest.MockAuthConfig(c)
			w := httptest.NewRecorder()
			oldOAuth := getOAuthClient
			getOAuthClient = func(ctx context.Context) (*http.Client, error) {
				return nil, fmt.Errorf("not today")
			}
			getRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("start", "123", "end", "456"),
			})
			getOAuthClient = oldOAuth
			So(w.Code, ShouldEqual, http.StatusInternalServerError)
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
