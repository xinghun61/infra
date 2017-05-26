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

	client "infra/monitoring/client/test"
	"infra/monitoring/messages"
	"infra/monorail"

	"golang.org/x/net/context"

	"github.com/julienschmidt/httprouter"

	"github.com/luci/gae/impl/dummy"
	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/urlfetch"
	"github.com/luci/luci-go/appengine/gaetesting"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/clock/testclock"
	"github.com/luci/luci-go/common/logging/gologger"
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
		c = gologger.StdConfig.Use(c)

		cl := testclock.New(testclock.TestRecentTimeUTC)
		c = clock.Set(c, cl)

		w := httptest.NewRecorder()

		tok, err := xsrf.Token(c)
		So(err, ShouldBeNil)
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
			revisionSummaryIdx := datastore.IndexDefinition{
				Kind:     "RevisionSummaryJSON",
				Ancestor: true,
				SortBy: []datastore.IndexColumn{
					{
						Property:   "Date",
						Descending: false,
					},
				},
			}
			indexes := []*datastore.IndexDefinition{&alertsIdx, &revisionSummaryIdx}
			datastore.GetTestable(c).AddIndexes(indexes...)

			Convey("/trees", func() {
				Convey("no trees yet", func() {
					GetTreesHandler(&router.Context{
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
					GetTreesHandler(&router.Context{
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
				contents, _ := json.Marshal(&messages.Alert{
					Key: "test",
				})
				alertJSON := &AlertJSON{
					ID:       "test",
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
					Resolved: false,
					Contents: []byte(contents),
				}
				oldRevisionSummaryJSON := &RevisionSummaryJSON{
					ID:       "rev1",
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
					Date:     time.Unix(1, 0).UTC(),
					Contents: []byte(contents),
				}
				newRevisionSummaryJSON := &RevisionSummaryJSON{
					ID:       "rev2",
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
					Date:     clock.Now(c),
					Contents: []byte(contents),
				}

				Convey("GET", func() {
					Convey("no alerts yet", func() {
						GetAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "oak"),
						})

						_, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						So(w.Code, ShouldEqual, 200)
					})

					So(datastore.Put(c, alertJSON), ShouldBeNil)
					So(datastore.Put(c, oldRevisionSummaryJSON), ShouldBeNil)
					So(datastore.Put(c, newRevisionSummaryJSON), ShouldBeNil)

					Convey("basic alerts", func() {
						GetAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "oak"),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						So(w.Code, ShouldEqual, 200)
						summary := &messages.AlertsSummary{}
						err = json.Unmarshal(r, &summary)
						So(err, ShouldBeNil)
						So(summary.Alerts, ShouldHaveLength, 1)
						So(summary.Alerts[0].Key, ShouldEqual, "test")
						So(summary.RevisionSummaries, ShouldHaveLength, 1)
						So(summary.RevisionSummaries, ShouldContainKey, "rev2")
					})

					Convey("trooper alerts", func() {
						ta := datastore.GetTestable(c)

						datastore.Put(c, &Tree{
							Name: "chromium",
						})

						alertsSummary := &messages.AlertsSummary{
							Timestamp: 1,
							Alerts: []messages.Alert{
								{
									Type: messages.AlertOfflineBuilder,
								},
							},
						}
						asBytes, err := json.Marshal(alertsSummary.Alerts[0])
						So(err, ShouldBeNil)

						datastore.Put(c, &AlertJSON{
							ID:       "1",
							Tree:     datastore.MakeKey(c, "Tree", "chromium"),
							Date:     time.Unix(1, 0).UTC(),
							Contents: asBytes,
						})
						ta.CatchupIndexes()

						GetAlertsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("tree", "trooper"),
						})

						r, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						body := string(r)
						So(w.Code, ShouldEqual, 200)
						So(body, ShouldEqual, `{"alerts":[{"key":"","title":"","body":"","severity":0,"time":0,"start_time":0,"links":null,"tags":null,"type":"offline-builder","extension":null,"tree":"chromium"}],"date":"1970-01-01T00:00:01Z","revision_summaries":null,"swarming":{"dead":null,"quarantined":null,"errors":["auth: the library is not properly configured"]},"timestamp":1}`)
					})

					Convey("getSwarmingAlerts", func() {
						// HACK:
						oldOAClient := getOAuthClient
						getOAuthClient = func(c context.Context) (*http.Client, error) {
							return &http.Client{}, nil
						}

						swarmingBasePath = "http://fakeurl"

						sa := getSwarmingAlerts(c)

						getOAuthClient = oldOAClient
						So(sa.Error, ShouldNotBeNil)
					})
				})

				Convey("POST", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					// Add an alert.
					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"alerts":[{"key": "test"}], "timestamp": 12345.0, "revision_summaries":{"123": {"git_hash": "123"}}}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					// Verify the expected alert.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")

					// Verify the revision summary.
					revisions := []*RevisionSummaryJSON{}
					q = datastore.NewQuery("RevisionSummaryJSON")
					So(datastore.GetAll(c, q, &revisions), ShouldBeNil)
					So(revisions, ShouldHaveLength, 1)
					summary := revisions[0]
					So(summary.Tree, ShouldResemble, alertJSON.Tree)
					rslt = make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(summary.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["git_hash"], ShouldEqual, "123")

					// Replace the alert.
					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"alerts":[{"key": "test2"}], "timestamp": 12345.0}`),
						Params:  makeParams("tree", "oak"),
					})

					r, err = ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body = string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					// Verify the expected alert.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					q = datastore.NewQuery("AlertJSON")
					q = q.Eq("Resolved", false)
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm = results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					rslt = make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test2")

					// Verify the original alert is resolved.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					q = datastore.NewQuery("AlertJSON")
					q = q.Eq("Resolved", true)
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm = results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.AutoResolved, ShouldEqual, true)
					rslt = make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")

					// Re-add original alert.
					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"alerts":[{"key": "test"}], "timestamp": 12345.0, "revision_summaries":{"123": {"git_hash": "123"}}}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err = ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body = string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					// Verify the expected alert.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					q = datastore.NewQuery("AlertJSON")
					q = q.Eq("Resolved", false)
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm = results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					rslt = make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")

					// Verify the second alert is resolved.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					q = datastore.NewQuery("AlertJSON")
					q = q.Eq("Resolved", true)
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm = results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.AutoResolved, ShouldEqual, true)
					rslt = make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test2")
				})

				Convey("POST auto-resolve many", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					for i := 0; i < 123; i++ {
						alert := &AlertJSON{
							ID:       fmt.Sprintf("test %d", i),
							Tree:     datastore.MakeKey(c, "Tree", "oak"),
							Resolved: false,
							Contents: []byte(contents),
						}
						So(datastore.Put(c, alert), ShouldBeNil)
					}

					// Add an alert.
					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"alerts":[{"key": "test"}], "timestamp": 12345.0, "revision_summaries":{"123": {"git_hash": "123"}}}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					// Verify the expected alert.
					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 124)
					resolvedCount := 0
					keyMatchCount := 0
					for _, itm := range results {
						if itm.Resolved {
							resolvedCount++
						}
						if itm.ID == "test" {
							keyMatchCount++
						}
						So(itm.Tree, ShouldResemble, alertJSON.Tree)
						rslt := make(map[string]interface{})
						So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
						So(rslt["key"], ShouldEqual, "test")
					}
					So(resolvedCount, ShouldEqual, 123)
					So(keyMatchCount, ShouldEqual, 1)
				})

				Convey("POST err", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`not valid json`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
				})

				Convey("POST err, valid but wrong json", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					PostAlertsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{}`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
				})

			})

			Convey("/alert", func() {
				contents, _ := json.Marshal(&messages.Alert{
					Key: "test",
				})
				alertJSON := &AlertJSON{
					ID:       "test",
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
					Resolved: false,
					Contents: []byte(contents),
				}
				Convey("POST", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					PostAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"key": "test", "body": "foo"}`),
						Params:  makeParams("tree", "oak", "key", "test"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.ID, ShouldEqual, "test")
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.Resolved, ShouldEqual, false)
					So(itm.AutoResolved, ShouldEqual, false)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")
					So(rslt["body"], ShouldEqual, "foo")
				})

				Convey("POST replace", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					So(datastore.Put(c, alertJSON), ShouldBeNil)

					PostAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"key": "test", "body": "foo"}`),
						Params:  makeParams("tree", "oak", "key", "test"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.ID, ShouldEqual, "test")
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.Resolved, ShouldEqual, false)
					So(itm.AutoResolved, ShouldEqual, false)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")
					So(rslt["body"], ShouldEqual, "foo")
				})

				Convey("POST resolved", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					alertJSON.Resolved = true
					So(datastore.Put(c, alertJSON), ShouldBeNil)

					PostAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"key": "test", "body": "foo"}`),
						Params:  makeParams("tree", "oak", "key", "test"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.ID, ShouldEqual, "test")
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.Resolved, ShouldEqual, true)
					So(itm.AutoResolved, ShouldEqual, false)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")
					So(rslt["body"], ShouldEqual, "foo")
				})

				Convey("POST auto-resolved", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					alertJSON.Resolved = true
					alertJSON.AutoResolved = true
					So(datastore.Put(c, alertJSON), ShouldBeNil)

					PostAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`{"key": "test", "body": "foo"}`),
						Params:  makeParams("tree", "oak", "key", "test"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(w.Code, ShouldEqual, 200)
					So(body, ShouldEqual, "")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.ID, ShouldEqual, "test")
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.Resolved, ShouldEqual, false)
					So(itm.AutoResolved, ShouldEqual, false)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")
					So(rslt["body"], ShouldEqual, "foo")
				})

				Convey("POST err", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					PostAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`not valid json`),
						Params:  makeParams("tree", "oak", "key", "test"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
				})
			})

			Convey("/resolve", func() {
				contents, _ := json.Marshal(&messages.Alert{
					Key: "test",
				})
				alertJSON := &AlertJSON{
					ID:       "test",
					Tree:     datastore.MakeKey(c, "Tree", "oak"),
					Resolved: false,
					Contents: []byte(contents),
				}
				makeResolve := func(data *ResolveRequest, tok string) string {
					change, err := json.Marshal(map[string]interface{}{
						"xsrf_token": tok,
						"data":       data,
					})
					So(err, ShouldBeNil)
					return string(change)
				}
				Convey("POST", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					So(datastore.Put(c, alertJSON), ShouldBeNil)

					// Resolve.
					req := &ResolveRequest{
						Keys:     make([]string, 1),
						Resolved: true,
					}
					req.Keys[0] = "test"
					ResolveAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(makeResolve(req, tok)),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusOK)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 200)

					resolveResponse := &ResolveResponse{}
					So(json.Unmarshal(r, resolveResponse), ShouldBeNil)
					So(resolveResponse.Keys, ShouldHaveLength, 1)
					So(resolveResponse.Keys[0], ShouldEqual, "test")
					So(resolveResponse.Resolved, ShouldEqual, true)

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldHaveLength, 1)
					itm := results[0]
					So(itm.Tree, ShouldResemble, alertJSON.Tree)
					So(itm.Resolved, ShouldEqual, true)
					So(itm.AutoResolved, ShouldEqual, false)
					rslt := make(map[string]interface{})
					So(json.NewDecoder(bytes.NewReader(itm.Contents)).Decode(&rslt), ShouldBeNil)
					So(rslt["key"], ShouldEqual, "test")
				})

				Convey("POST non-existant", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					// Resolve.
					req := &ResolveRequest{
						Keys:     make([]string, 1),
						Resolved: true,
					}
					req.Keys[0] = "test"
					ResolveAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(makeResolve(req, tok)),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusInternalServerError)

					r, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					body := string(r)
					So(body, ShouldContainSubstring, "not found")

					datastore.GetTestable(c).CatchupIndexes()
					results = []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)
				})

				Convey("POST err", func() {
					q := datastore.NewQuery("AlertJSON")
					results := []*AlertJSON{}
					So(datastore.GetAll(c, q, &results), ShouldBeNil)
					So(results, ShouldBeEmpty)

					ResolveAlertHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makePostRequest(`not valid json`),
						Params:  makeParams("tree", "oak"),
					})

					So(w.Code, ShouldEqual, http.StatusBadRequest)
				})
			})

			Convey("/annotations", func() {
				Convey("GET", func() {
					Convey("no annotations yet", func() {
						GetAnnotationsHandler(&router.Context{
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
						Bugs:             []string{"111", "222"},
						SnoozeTime:       123123,
						ModificationTime: datastore.RoundTime(clock.Now(c).Add(4 * time.Hour)),
					}

					So(datastore.Put(c, ann), ShouldBeNil)
					datastore.GetTestable(c).CatchupIndexes()

					Convey("basic annotation", func() {
						GetAnnotationsHandler(&router.Context{
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
						PostAnnotationsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makePostRequest(""),
							Params:  makeParams("annKey", "foobar", "action", "lolwut"),
						})

						So(w.Code, ShouldEqual, 404)
					})

					Convey("invalid json", func() {
						PostAnnotationsHandler(&router.Context{
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
						PostAnnotationsHandler(&router.Context{
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
						ann := &Annotation{
							Key:              "foobar",
							KeyDigest:        fmt.Sprintf("%x", sha1.Sum([]byte("foobar"))),
							ModificationTime: datastore.RoundTime(clock.Now(c)),
						}
						change := map[string]interface{}{}
						Convey("snoozeTime", func() {
							change["snoozeTime"] = 123123
							PostAnnotationsHandler(&router.Context{
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
						})

						Convey("bugs", func() {
							change["bugs"] = []string{"123123"}
							PostAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(makeChange(change, tok)),
								Params:  makeParams("annKey", "foobar", "action", "add"),
							})

							So(w.Code, ShouldEqual, 200)

							So(datastore.Get(c, ann), ShouldBeNil)
							So(ann.Bugs, ShouldResemble, []string{"123123"})
						})

						Convey("bad change", func() {
							change["bugs"] = []string{"ooops"}
							w = httptest.NewRecorder()
							PostAnnotationsHandler(&router.Context{
								Context: c,
								Writer:  w,
								Request: makePostRequest(makeChange(change, tok)),
								Params:  makeParams("annKey", "foobar", "action", "add"),
							})

							So(w.Code, ShouldEqual, 400)

							So(datastore.Get(c, ann), ShouldNotBeNil)
						})
					})

					Convey("remove", func() {
						Convey("can't remove non-existant annotation", func() {
							PostAnnotationsHandler(&router.Context{
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

							PostAnnotationsHandler(&router.Context{
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

				c = urlfetch.Set(c, &client.MockGitilesTransport{
					Responses: map[string]string{
						gkTreesInternalURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
						gkTreesCorpURL: `{    "chromium": {
        "build-db": "waterfall_build_db.json",
        "masters": {
            "https://build.chromium.org/p/chromium": ["*"]
        },
        "open-tree": true,
        "password-file": "/creds/gatekeeper/chromium_status_password",
        "revision-properties": "got_revision_cp",
        "set-status": true,
        "status-url": "https://chromium-status.appspot.com",
        "track-revisions": true
    }}`,
						gkConfigInternalURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,
						gkConfigCorpURL: `
{
  "comment": ["This is a configuration file for gatekeeper_ng.py",
              "Look at that for documentation on this file's format."],
  "masters": {
    "https://build.chromium.org/p/chromium": [
      {
        "categories": [
          "chromium_tree_closer"
        ],
        "builders": {
          "Win": {
            "categories": [
              "chromium_windows"
            ]
          },
          "*": {}
        }
      }
    ]
   }
}`,

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
				Convey("ok", func() {
					GetRestartingMastersHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
						Params:  makeParams("tree", "chromium"),
					})
					_, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 200)
				})

				Convey("trooper restarts", func() {
					GetRestartingMastersHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
						Params:  makeParams("tree", "trooper"),
					})
					_, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 200)
				})

				Convey("unrecognized tree", func() {
					GetRestartingMastersHandler(&router.Context{
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

			})

			Convey("/bugqueue", func() {
				Convey("getBugsFromMonorail", func() {
					// HACK
					oldOAClient := getOAuthClient
					getOAuthClient = func(c context.Context) (*http.Client, error) {
						return &http.Client{}, nil
					}
					_, err = getBugsFromMonorail(c, "label:test", 0)
					So(err, ShouldNotBeNil)
					getOAuthClient = oldOAClient
				})

				Convey("mock getBugsFromMonorail", func() {
					getBugsFromMonorail = func(c context.Context, q string,
						can monorail.IssuesListRequest_CannedQuery) (*monorail.IssuesListResponse, error) {
						res := &monorail.IssuesListResponse{
							Items:        []*monorail.Issue{},
							TotalResults: 0,
						}
						return res, nil
					}
					Convey("get bug queue handler", func() {
						GetBugQueueHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
						})

						b, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						So(w.Code, ShouldEqual, 200)
						So(string(b), ShouldEqual, "{}")
					})

					Convey("refresh bug queue handler", func() {
						RefreshBugQueueHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
						})

						b, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						So(w.Code, ShouldEqual, 200)
						So(string(b), ShouldEqual, "{}")
					})

					Convey("refresh bug queue", func() {
						// HACK:
						oldOAClient := getOAuthClient
						getOAuthClient = func(c context.Context) (*http.Client, error) {
							return &http.Client{}, nil
						}

						_, err := refreshBugQueue(c, "label")
						So(err, ShouldBeNil)
						getOAuthClient = oldOAClient
					})

					Convey("get uncached bugs", func() {
						GetUncachedBugsHandler(&router.Context{
							Context: c,
							Writer:  w,
							Request: makeGetRequest(),
							Params:  makeParams("label", "infra-troopers"),
						})

						b, err := ioutil.ReadAll(w.Body)
						So(err, ShouldBeNil)
						So(w.Code, ShouldEqual, 200)
						So(string(b), ShouldEqual, "{}")
					})

					Convey("get alternate email", func() {
						e := getAlternateEmail("test@chromium.org")
						So(e, ShouldEqual, "test@google.com")

						e = getAlternateEmail("test@google.com")
						So(e, ShouldEqual, "test@chromium.org")
					})
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

					FlushOldAnnotationsHandler(ctx)
				})
			})

			Convey("refreshAnnotations", func() {
				Convey("handler", func() {
					RefreshAnnotationsHandler(&router.Context{
						Context: c,
						Writer:  w,
						Request: makeGetRequest(),
					})

					b, err := ioutil.ReadAll(w.Body)
					So(err, ShouldBeNil)
					So(w.Code, ShouldEqual, 200)
					So(string(b), ShouldEqual, "{}")
				})

				Convey("inner function", func() {
					oldGetBugs := getBugsFromMonorail
					mrResp := &monorail.IssuesListResponse{
						Items:        []*monorail.Issue{},
						TotalResults: 0,
					}

					var mrErr error
					var query string
					getBugsFromMonorail = func(c context.Context, q string,
						can monorail.IssuesListRequest_CannedQuery) (*monorail.IssuesListResponse, error) {
						query = q
						return mrResp, mrErr
					}

					ann := &Annotation{
						Bugs: []string{"111111"},
					}
					So(datastore.Put(c, ann), ShouldBeNil)
					datastore.GetTestable(c).CatchupIndexes()

					Convey("one bug", func() {
						// Don't care about the return value for now.
						_, err := refreshAnnotations(c, nil)

						So(err, ShouldBeNil)
						So(query, ShouldEqual, "id:111111")
					})

					ann = &Annotation{
						Bugs: []string{"111111", "222222"},
					}
					So(datastore.Put(c, ann), ShouldBeNil)
					datastore.GetTestable(c).CatchupIndexes()

					Convey("de-dup", func() {
						// Don't care about the return value for now.
						_, err := refreshAnnotations(c, nil)

						So(err, ShouldBeNil)
						So(query, ShouldEqual, "id:111111,222222")
					})
					getBugsFromMonorail = oldGetBugs
				})
			})
		})

		Convey("clientmon", func() {
			body := &eCatcherReq{XSRFToken: tok}
			bodyBytes, err := json.Marshal(body)
			So(err, ShouldBeNil)
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makePostRequest(string(bodyBytes)),
				Params:  makeParams("xsrf_token", tok),
			}

			PostClientMonHandler(ctx)
			So(w.Code, ShouldEqual, 200)
		})

		Convey("treelogo", func() {
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
			ctx := &router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
				Params:  makeParams("tree", "chromium"),
			}

			getTreeLogo(ctx, "", &noopSigner{fmt.Errorf("fail")})
			So(w.Code, ShouldEqual, 500)
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
		// crbug.com/725595 - This test does real network access.
		SkipConvey("ok", func() {
			c := gaetesting.TestingContext()
			c = authtest.MockAuthConfig(c)
			w := httptest.NewRecorder()

			GetRevRangeHandler(&router.Context{
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
			GetRevRangeHandler(&router.Context{
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

			GetRevRangeHandler(&router.Context{
				Context: c,
				Writer:  w,
				Request: makeGetRequest(),
			})

			So(w.Code, ShouldEqual, 400)
		})
	})
}
