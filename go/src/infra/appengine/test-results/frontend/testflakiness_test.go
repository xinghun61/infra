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
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
	bigquery "google.golang.org/api/bigquery/v2"
)

type expectedRequest struct {
	Path      string
	Query     string
	PageToken string
	Response  string
	Processed bool
}

type fakeBQHandler struct {
	C                C
	ExpectedRequests []expectedRequest
	Mutex            sync.Mutex
}

func parseQuery(body io.ReadCloser, c C) string {
	bodyBytes, err := ioutil.ReadAll(body)
	c.So(err, ShouldBeNil)
	if len(bodyBytes) == 0 {
		return ""
	}

	var req bigquery.QueryRequest
	err = json.Unmarshal(bodyBytes, &req)
	c.So(err, ShouldBeNil)
	c.So(req.TimeoutMs, ShouldEqual, 5000)
	return req.Query
}

func (h *fakeBQHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	query := parseQuery(r.Body, h.C)
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
		fmt.Fprintln(w, er.Response)
		er.Processed = true
		return
	}

	panic(fmt.Sprintf("Unexpected request: %#v %#v %#v", path, query, pageToken))
}

func TestGetFlakinessGroups(t *testing.T) {
	t.Parallel()

	Convey("getFlakinessGroups", t, func(c C) {
		handler := fakeBQHandler{
			C: c,
			ExpectedRequests: []expectedRequest{
				{
					Path:  "/projects/test-results-hrd/queries",
					Query: teamsQuery,
					Response: `{"totalRows": "2", "jobReference": {"jobId": "x"},
											"rows": [{"f": [{"v": "team1"}]}, {"f": [{}]}]}`,
				},
				{
					Path:  "/projects/test-results-hrd/queries",
					Query: dirsQuery,
					Response: `{"totalRows": "3", "jobReference": {"jobId": "y"},
											"pageToken": "zz",
											"rows": [{"f": [{"v": "dir1"}]}, {"f": [{}]}]}`,
				},
				{
					Path:      "/projects/test-results-hrd/queries/y",
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
		ctx := memory.Use(context.Background())

		groups, err := getFlakinessGroups(ctx, bq)
		So(err, ShouldBeNil)
		So(Group{Name: "team1", Kind: "team"}, ShouldBeIn, groups)
		So(Group{Kind: "unknown-team"}, ShouldBeIn, groups)
		So(Group{Name: "dir1", Kind: "dir"}, ShouldBeIn, groups)
		So(Group{Name: "dir2", Kind: "dir"}, ShouldBeIn, groups)
		So(Group{Kind: "unknown-dir"}, ShouldBeIn, groups)
	})
}

func TestGetFlakinessData(t *testing.T) {
	// TODO(sergiyb): Add tests to getFlakinessData when it's implemented.
	Convey("getFlakinessData", t, nil)
}
