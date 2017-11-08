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
	"strconv"
	"sync"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/gae/impl/memory"
	"go.chromium.org/luci/common/proto/milo"
	milo_api "go.chromium.org/luci/milo/api/proto"
	"go.chromium.org/luci/server/auth/authtest"
	"go.chromium.org/luci/server/router"
	"golang.org/x/net/context"
	bigquery "google.golang.org/api/bigquery/v2"
	grpc "google.golang.org/grpc"
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
		"Unexpected request:\nPath: %v\nQuery: %v\nParams: %v\nPage Token: %v\n\n",
		path, query, params, pageToken)
	errMsg += "Expected requests:\n"
	for _, er := range h.ExpectedRequests {
		if !er.Processed {
			errMsg += fmt.Sprintf(
				" - Path: %v\n   Query: %v\n   Params: %v\n   Page Token: %v\n\n",
				er.Path, er.Query, er.Params, er.PageToken)
		}
	}
	h.C.So(errMsg, ShouldBeEmpty)
}

func init() {
	// Force tests to do no retries. If a test needs to be added that does need
	// retries it must not be configured to run in parallel with others.
	retryFactory = nil
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
	t.Parallel()

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

type mockBuildInfoClient struct {
	miloDB map[string]string // key is 'master/builder/build_number', value is step name
	c      C
}

func (cl *mockBuildInfoClient) Get(ctx context.Context, in *milo_api.BuildInfoRequest, opts ...grpc.CallOption) (*milo_api.BuildInfoResponse, error) {
	key := in.GetBuildbot().MasterName + "/" + in.GetBuildbot().BuilderName + "/" + strconv.FormatInt(in.GetBuildbot().BuildNumber, 10)
	stepName, ok := cl.miloDB[key]
	cl.c.So(ok, ShouldBeTrue)
	resp := &milo_api.BuildInfoResponse{
		Project: "chromium",
		Step: &milo.Step{
			Name: "steps",
			Substep: []*milo.Step_Substep{
				{
					Substep: &milo.Step_Substep_Step{
						Step: &milo.Step{
							Name: stepName,
							StdoutStream: &milo.LogdogStream{
								Name: "recipes/steps/" + stepName + "/0/stdout",
							},
						},
					},
				},
			},
		},
		AnnotationStream: &milo.LogdogStream{
			Server: "luci-logdog.appspot.com",
			Prefix: "bb/" + key,
		},
	}
	return resp, nil
}

type mockTestFlakinessService struct {
	bic mockBuildInfoClient
}

func (p mockTestFlakinessService) GetBuildInfoClient(ctx context.Context) (milo_api.BuildInfoClient, error) {
	return &p.bic, nil
}

func (p mockTestFlakinessService) GetBQService(aeCtx context.Context) (*bigquery.Service, error) {
	return nil, nil
}

func TestFlakinessData(t *testing.T) {
	t.Parallel()

	Convey("getFlakinessData", t, func(c C) {
		handler := fakeBQHandler{
			C: c,
			ExpectedRequests: []*expectedRequest{
				{
					Query: flakyBuildsQuery,
					Params: `[{"name":"testname","parameterType":{"type":"STRING"},` +
						`"parameterValue":{"value":"Foo.Bar"}}]`,
					Path: "/projects/test-results-hrd/queries",
					Response: `{"totalRows": "2",
											"jobReference": {"jobId": "x"},
											"jobComplete": true,
											"rows": [
												{"f": [{"v": "master.master1"},
												       {"v": "builder1"},
												       {"v": "1"},
												       {"v": "step1"}]},
												{"f": [{"v": "master2"},
												       {"v": "builder2"},
												       {"v": "2"},
												       {"v": "step2"}]}
											]}`,
				},
				{
					Query: cqFlakyBuildsQuery,
					Params: `[{"name":"testname","parameterType":{"type":"STRING"},` +
						`"parameterValue":{"value":"Foo.Bar"}}]`,
					Path: "/projects/test-results-hrd/queries",
					Response: `{"totalRows": "2",
											"jobReference": {"jobId": "x"},
											"jobComplete": true,
											"rows": [
												{"f": [{"v": "master3"},
												       {"v": "builder3"},
												       {"v": "3"},
												       {"v": "4"},
												       {"v": "step3"}]},
												{"f": [{"v": "master4"},
												       {"v": "builder4"},
												       {"v": "5"},
												       {"v": "6"},
												       {"v": "step4"}]}
											]}`,
				},
			},
		}

		server := httptest.NewServer(&handler)
		bq, err := bigquery.New(&http.Client{})
		So(err, ShouldBeNil)
		bq.BasePath = server.URL + "/"
		ctx := memory.UseWithAppID(context.Background(), "test-results-hrd")
		ctx = authtest.MockAuthConfig(ctx)

		bic := mockBuildInfoClient{
			miloDB: map[string]string{
				"master1/builder1/1": "step1",
				"master2/builder2/2": "step2",
				"master3/builder3/3": "step3",
				"master3/builder3/4": "step3",
				"master4/builder4/5": "step4",
				"master4/builder4/6": "step4",
			},
			c: c,
		}

		data, err := getFlakinessData(ctx, mockTestFlakinessService{bic}, bq, "Foo.Bar")
		So(err, ShouldBeNil)

		So(data.FlakyBuilds, ShouldResemble, []FlakyBuild{
			{
				"https://ci.chromium.org/buildbot/master1/builder1/1",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster1%2Fbuilder1%2F1%2F%2B%2Frecipes%2Fsteps%2Fstep1%2F0%2Fstdout",
			},
			{
				"https://ci.chromium.org/buildbot/master2/builder2/2",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster2%2Fbuilder2%2F2%2F%2B%2Frecipes%2Fsteps%2Fstep2%2F0%2Fstdout",
			},
		})
		So(data.CQFlakyBuilds, ShouldResemble, []CQFlakyBuild{
			{
				"https://ci.chromium.org/buildbot/master3/builder3/3",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster3%2Fbuilder3%2F3%2F%2B%2Frecipes%2Fsteps%2Fstep3%2F0%2Fstdout",
				"https://ci.chromium.org/buildbot/master3/builder3/4",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster3%2Fbuilder3%2F4%2F%2B%2Frecipes%2Fsteps%2Fstep3%2F0%2Fstdout",
			},
			{
				"https://ci.chromium.org/buildbot/master4/builder4/5",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster4%2Fbuilder4%2F5%2F%2B%2Frecipes%2Fsteps%2Fstep4%2F0%2Fstdout",
				"https://ci.chromium.org/buildbot/master4/builder4/6",
				"https://luci-logdog.appspot.com/v/?s=chromium%2Fbb%2Fmaster4%2Fbuilder4%2F6%2F%2B%2Frecipes%2Fsteps%2Fstep4%2F0%2Fstdout",
			},
		})
	})
}

func TestCachedDataHandler(t *testing.T) {
	t.Parallel()

	Convey("cachedDataHandler", t, func(c C) {
		rec := httptest.NewRecorder()
		ctx := &router.Context{
			Context: memory.Use(context.Background()),
			Writer:  rec,
		}

		calledFunc := false
		cachedDataHandler(
			ctx, mockTestFlakinessService{}, "mockFunc", "mockKey", []string{},
			func(context.Context, testFlakinessService, *bigquery.Service) (interface{}, error) {
				calledFunc = true
				return []string{"abc", "cde", "efg"}, nil
			},
		)
		So(calledFunc, ShouldBeTrue)
		So(rec.Result().StatusCode, ShouldEqual, http.StatusOK)
		So(rec.Body.String(), ShouldEqual, "[\"abc\",\"cde\",\"efg\"]")
		rec.Body.Reset()

		calledFunc = false
		cachedDataHandler(
			ctx, mockTestFlakinessService{}, "mockFunc", "mockKey", []string{},
			func(context.Context, testFlakinessService, *bigquery.Service) (interface{}, error) {
				calledFunc = true
				return []string{"abc", "cde", "efg"}, nil
			},
		)
		So(calledFunc, ShouldBeFalse)
		So(rec.Result().StatusCode, ShouldEqual, http.StatusOK)
		So(rec.Body.String(), ShouldEqual, "[\"abc\",\"cde\",\"efg\"]")
	})
}
