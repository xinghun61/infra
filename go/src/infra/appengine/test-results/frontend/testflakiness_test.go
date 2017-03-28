// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"

	"github.com/luci/gae/impl/memory"
	"github.com/luci/luci-go/server/router"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	bigquery "google.golang.org/api/bigquery/v2"
)

type expectedRequest struct {
	Path      string
	Query     string
	PageToken string
	Response  string
	Params    string
	Processed bool
}

type fakeBQHandler struct {
	C                C
	ExpectedRequests []*expectedRequest
	Mutex            sync.Mutex
}

func parseQuery(body io.Reader, c C) (string, string) {
	bodyBytes, err := ioutil.ReadAll(body)
	c.So(err, ShouldBeNil)
	if len(bodyBytes) == 0 {
		return "", ""
	}

	var req bigquery.QueryRequest
	err = json.Unmarshal(bodyBytes, &req)
	c.So(err, ShouldBeNil)

	var params string
	if len(req.QueryParameters) > 0 {
		paramBytes, err := json.Marshal(req.QueryParameters)
		c.So(err, ShouldBeNil)
		params = string(paramBytes)
	}
	return req.Query, params
}

func (h *fakeBQHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	query, params := parseQuery(r.Body, h.C)
	pageToken := r.URL.Query().Get("pageToken")

	// Make sure that all modifications to ExpectedQueries are synchronized.
	h.Mutex.Lock()
	defer h.Mutex.Unlock()

	for _, er := range h.ExpectedRequests {
		if er.Processed {
			continue
		}
		if er.Path != path {
			continue
		}
		if er.Query != query {
			continue
		}
		if er.PageToken != pageToken {
			continue
		}
		if er.Params != params {
			continue
		}
		fmt.Fprintln(w, er.Response)
		er.Processed = true
		return
	}

	errMsg := fmt.Sprintf(
		"Unexpected request: %#v %#v %#v %#v\n", path, query, params, pageToken)
	detailedMsg := errMsg + "Expected requests:\n"
	for _, er := range h.ExpectedRequests {
		if !er.Processed {
			detailedMsg += fmt.Sprintf(
				" - %#v %#v %#v %#v\n", er.Path, er.Query, er.Params, er.PageToken)
		}
	}
	h.C.Print(detailedMsg)
	h.C.So(errMsg, ShouldBeEmpty)
}

func TestWriteErrorAndResponse(t *testing.T) {
	t.Parallel()

	Convey("writeError and writeResponse", t, func() {
		rec := httptest.NewRecorder()
		ctx := &router.Context{
			Context: memory.UseWithAppID(context.Background(), "test-results-hrd"),
			Writer:  rec,
		}

		Convey("writeError", func() {
			writeError(ctx, nil, "testFunc", "test message")

			So(rec.Result().StatusCode, ShouldEqual, http.StatusInternalServerError)
			So(rec.Body.String(), ShouldEqual, "Internal Server Error\n")
		})

		Convey("writeResponse", func() {
			type TestType struct {
				X string `json:"x"`
				Y string `json:"y,omitempty"`
			}

			writeResponse(ctx, "testFunc", TestType{X: "y", Y: ""})

			So(rec.Result().StatusCode, ShouldEqual, http.StatusOK)
			So(rec.Body.String(), ShouldEqual, "{\"x\":\"y\"}")
		})
	})
}

func TestFlakinessGroups(t *testing.T) {
	t.Parallel()

	Convey("getFlakinessGroups", t, func(c C) {
		handler := fakeBQHandler{
			C: c,
			ExpectedRequests: []*expectedRequest{
				{
					Path:  "/projects/test-results-hrd/queries",
					Query: teamsQuery,
					Response: `{"jobReference": {"jobId": "x"},
											"jobComplete": false}`,
				},
				{
					Path: "/projects/test-results-hrd/queries/x",
					Response: `{"totalRows": "2",
											"jobReference": {"jobId": "x"},
											"jobComplete": true,
											"rows": [{"f": [{"v": "team1"}]}, {"f": [{}]}]}`,
				},
				{
					Path:  "/projects/test-results-hrd/queries",
					Query: suitesQuery,
					Response: `{"totalRows": "1",
											"jobReference": {"jobId": "y"},
											"jobComplete": true,
											"rows": [{"f": [{"v": "MySuite"}]}]}`,
				},
				{
					Path:  "/projects/test-results-hrd/queries",
					Query: dirsQuery,
					Response: `{"totalRows": "3",
											"jobReference": {"jobId": "z"},
											"jobComplete": true,
											"pageToken": "zz",
											"rows": [{"f": [{"v": "dir1"}]}, {"f": [{}]}]}`,
				},
				{
					Path:      "/projects/test-results-hrd/queries/z",
					PageToken: "zz",
					Response: `{"totalRows": "3", "jobReference": {"jobId": "y"},
											"rows": [{"f": [{"v": "dir2"}]}]}`,
				},
			},
		}

		server := httptest.NewServer(&handler)
		bq, err := bigquery.New(&http.Client{})
		So(err, ShouldBeNil)
		bq.BasePath = server.URL + "/"
		ctx := memory.UseWithAppID(context.Background(), "test-results-hrd")

		groups, err := getFlakinessGroups(ctx, bq)
		So(err, ShouldBeNil)
		So(Group{Name: "team1", Kind: TeamKind}, ShouldBeIn, groups)
		So(Group{Name: UnknownTeamKind, Kind: UnknownTeamKind}, ShouldBeIn, groups)
		So(Group{Name: "MySuite", Kind: TestSuiteKind}, ShouldBeIn, groups)
		So(Group{Name: "dir1", Kind: DirKind}, ShouldBeIn, groups)
		So(Group{Name: "dir2", Kind: DirKind}, ShouldBeIn, groups)
		So(Group{Name: UnknownDirKind, Kind: UnknownDirKind}, ShouldBeIn, groups)
	})
}

func TestFlakinessList(t *testing.T) {
	Convey("getFlakinessList", t, func(c C) {
		handler := fakeBQHandler{
			C: c,
			ExpectedRequests: []*expectedRequest{
				{
					Path: "/projects/test-results-hrd/queries",
					Response: `{"totalRows": "2",
											"jobReference": {"jobId": "x"},
											"jobComplete": true,
											"rows": [
												{"f": [
													{"v": "test1"},
													{"v": "unittests"},
													{"v": "287"},
													{"v": "8318"},
													{"v": "0.0345"},
													{"v": "35"}
												]},
												{"f": [
													{"v": "test2"},
													{"v": "unittests"},
													{"v": "2"},
													{"v": "4562"},
													{"v": "0.0004"},
													{"v": "0"}
												]}
											]}`,
				},
			},
		}

		server := httptest.NewServer(&handler)
		bq, err := bigquery.New(&http.Client{})
		So(err, ShouldBeNil)
		bq.BasePath = server.URL + "/"
		ctx := memory.UseWithAppID(context.Background(), "test-results-hrd")

		Convey("for tests in a dir", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE layout_test_dir = @groupname")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"foo"}}]`
			data, err := getFlakinessList(ctx, bq, Group{Name: "foo", Kind: DirKind})
			So(err, ShouldBeNil)
			So(data, ShouldResemble, []FlakinessListItem{
				{
					TestName:           "test1",
					NormalizedStepName: "unittests",
					TotalFlakyFailures: 287,
					TotalTries:         8318,
					Flakiness:          0.0345,
					CQFalseRejections:  35,
				},
				{
					TestName:           "test2",
					NormalizedStepName: "unittests",
					TotalFlakyFailures: 2,
					TotalTries:         4562,
					Flakiness:          0.0004,
					CQFalseRejections:  0,
				},
			})
		})

		Convey("for tests in a team", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE layout_test_team = @groupname")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"foo"}}]`
			_, err := getFlakinessList(ctx, bq, Group{Name: "foo", Kind: TeamKind})
			So(err, ShouldBeNil)
		})

		Convey("for tests in unknown dir", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE layout_test_dir is Null")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"unknown-dir"}}]`
			_, err := getFlakinessList(
				ctx, bq, Group{Name: UnknownDirKind, Kind: UnknownDirKind})
			So(err, ShouldBeNil)
		})

		Convey("for tests owned by an unknown team", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE layout_test_team is Null")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"unknown-team"}}]`
			_, err := getFlakinessList(
				ctx, bq, Group{Name: UnknownTeamKind, Kind: UnknownTeamKind})
			So(err, ShouldBeNil)
		})

		Convey("for tests in a particular test suite", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE regexp_contains(test_name, concat('^', @groupname, '[.#]'))")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"FooBar"}}]`
			_, err := getFlakinessList(
				ctx, bq, Group{Name: "FooBar", Kind: TestSuiteKind})
			So(err, ShouldBeNil)
		})

		Convey("for tests containing a substring", func() {
			handler.ExpectedRequests[0].Query =
				fmt.Sprintf(flakesQuery, "WHERE strpos(test_name, @groupname) != 0")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"FooBar"}}]`
			_, err := getFlakinessList(
				ctx, bq, Group{Name: "FooBar", Kind: SearchKind})
			So(err, ShouldBeNil)
		})

		Convey("for all tests", func() {
			handler.ExpectedRequests[0].Query = fmt.Sprintf(flakesQuery, "")
			handler.ExpectedRequests[0].Params =
				`[{"name":"groupname","parameterType":{"type":"STRING"},` +
					`"parameterValue":{"value":"all"}}]`
			_, err := getFlakinessList(
				ctx, bq, Group{Name: AllKind, Kind: AllKind})
			So(err, ShouldBeNil)
		})
	})
}
