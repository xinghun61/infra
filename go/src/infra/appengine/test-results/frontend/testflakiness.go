// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/luci/gae/service/info"
	"github.com/luci/gae/service/memcache"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/proto/milo"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/sync/parallel"
	"github.com/luci/luci-go/grpc/prpc"
	"github.com/luci/luci-go/logdog/common/types"
	"github.com/luci/luci-go/logdog/common/viewer"
	"github.com/luci/luci-go/luci_config/common/cfgtypes"
	milo_api "github.com/luci/luci-go/milo/api/proto"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/router"

	"golang.org/x/net/context"
	"golang.org/x/oauth2/google"
	bigquery "google.golang.org/api/bigquery/v2"
	"google.golang.org/appengine"
)

const teamsQuery = `
  SELECT
    layout_test_team
  FROM
    plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
  GROUP BY
    layout_test_team;`

const dirsQuery = `
  SELECT
    layout_test_dir
  FROM
    plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
  GROUP BY
    layout_test_dir;`

const suitesQuery = `
  SELECT
    if(regexp_contains(test_name, r'^org\..*#.*$'),
       regexp_extract(test_name, r'^(org\..*)#.*$'),
       regexp_extract(test_name, r'^([^\.\/]+)\.[^\/]+(?:\/[^\.]+)?$')) as suite
  FROM
    plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
  GROUP BY
    suite
  HAVING
    suite is not Null;`

const flakesQuery = `
  SELECT
    test_name,
    normalized_step_name,
    total_flaky_failures,
    total_tries,
    flakiness,
    cq_false_rejections
  FROM
    plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
  %s
  ORDER BY
    cq_false_rejections DESC,
    flakiness DESC
  LIMIT
    1000;`

const flakyBuildsQuery = `
  SELECT
    master, builder, build_number, step_name
  FROM
    plx.google.chrome_infra.recent_flaky_test_failures.all
  WHERE
    test_name = @testname
  LIMIT
    100;`

const cqFlakyBuildsQuery = `
  SELECT
    master,
    builder,
    passed_build_number,
    failed_build_number,
    step_name
  FROM
    plx.google.chrome_infra.test_cq_flaky_builds.all
  WHERE
    test_name = @testname
  LIMIT
    100;`

// Set 50 second timeout for the BigQuery queries, which leaves 10 seconds for
// overhead before HTTP timeout. The query will actually continue to run after
// the timeout and we wait for results in a loop.
const bqQueryTimeout = 50 * 1000

// Different kinds of groups to be used for Group struct below.
const (
	// Represents group of tests owned a team with specified name.
	TeamKind = "team"

	// Represents groups of tests in a diretory in the source code with path
	// specified as name.
	DirKind = "dir"

	// Represents group of tests not owned by any team.
	UnknownTeamKind = "unknown-team"

	// Represents group of tests for which we do not know the containing
	// directory.
	UnknownDirKind = "unknown-dir"

	// Represents a group of tests belonging to the test suite with specified
	// name.
	TestSuiteKind = "test-suite"

	// Represents a group of tests containing substring specified as name.
	SearchKind = "search"

	// Represents group of all tests. Practically will show 1000 most flaky tests.
	AllKind = "all"
)

const (
	flakinessGroupsKey       = "flakinessGroups"
	flakinessListKeyTemplate = "flakinessList-%s-%s"
	flakinessDataKeyTemplate = "flakinessData-%s"
)

// FlakinessListItem represents aggregate flakiness data about a flaky test.
// This information is shown in a table with 1 row per test.
type FlakinessListItem struct {
	TestName           string  `json:"test_name"`
	Flakiness          float64 `json:"flakiness"`
	NormalizedStepName string  `json:"normalized_step_name"`
	TotalFlakyFailures uint64  `json:"total_flaky_failures"`
	TotalTries         uint64  `json:"total_tries"`
	// TODO(sergiyb): rename to CQFlakyBuilds
	CQFalseRejections uint64 `json:"cq_false_rejections"`
}

// FlakyBuild represents a build in which a test has passed and failed.
type FlakyBuild struct {
	BuildURL string `json:"build_url"`
	LogURL   string `json:"log_url"`
}

// CQFlakyBuild represent a build, which has failed due to a flaky test.
type CQFlakyBuild struct {
	PassedBuildURL string `json:"passed_build_url"`
	PassedLogURL   string `json:"passed_log_url"`
	FailedBuildURL string `json:"failed_build_url"`
	FailedLogURL   string `json:"failed_log_url"`
}

// FlakyTestDetails represents detailed information about a flaky test.
type FlakyTestDetails struct {
	FlakyBuilds   []FlakyBuild   `json:"flaky_builds"`
	CQFlakyBuilds []CQFlakyBuild `json:"cq_flaky_builds"`
}

// Group represents infromation about flakiness of a group of tests.
type Group struct {
	Name string `json:"name"`
	Kind string `json:"kind"`
}

func writeError(ctx *router.Context, err error, funcName string, msg string) {
	reason := fmt.Sprintf("%s: %s", funcName, msg)
	if err == nil {
		err = errors.New(reason)
	}

	errors.Log(ctx.Context, errors.Annotate(err).Reason(reason).Err())
	http.Error(ctx.Writer, "Internal Server Error", http.StatusInternalServerError)
}

func writeResponse(ctx *router.Context, funcName string, data interface{}) {
	res, err := json.Marshal(data)
	if err != nil {
		writeError(ctx, err, funcName, "failed to marshal JSON")
		return
	}

	if _, err = ctx.Writer.Write(res); err != nil {
		writeError(ctx, err, funcName, "failed to write HTTP response")
	}
}

func getFlakinessList(ctx context.Context, bq *bigquery.Service, group Group) ([]FlakinessListItem, error) {
	var filter string
	switch group.Kind {
	case TeamKind:
		// TODO(sergiyb): Change this when we have a way to detect which team owns a
		// given test (other than layout test).
		filter = "WHERE layout_test_team = @groupname"
	case DirKind:
		filter = "WHERE layout_test_dir = @groupname"
	case UnknownTeamKind:
		filter = "WHERE layout_test_team is Null"
	case UnknownDirKind:
		filter = "WHERE layout_test_dir is Null"
	case TestSuiteKind:
		filter = "WHERE regexp_contains(test_name, concat('^', @groupname, '[.#]'))"
	case SearchKind:
		filter = "WHERE strpos(test_name, @groupname) != 0"
	case AllKind:
		filter = ""
	default:
		return nil, errors.New("unknown group kind " + group.Kind)
	}

	queryParams := []*bigquery.QueryParameter{
		{
			Name:           "groupname",
			ParameterType:  &bigquery.QueryParameterType{Type: "STRING"},
			ParameterValue: &bigquery.QueryParameterValue{Value: group.Name},
		},
	}

	rows, err := executeBQQuery(
		ctx, bq, fmt.Sprintf(flakesQuery, filter), queryParams)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	data := make([]FlakinessListItem, 0, len(rows))
	for _, row := range rows {
		name, ok := row.F[0].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string test name column")
		}

		normalizedStepName, ok := row.F[1].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for normalized_step_name column")
		}

		totalFlakyFailuresStr, ok := row.F[2].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for total_flaky_failures column")
		}

		totalFlakyFailures, err := strconv.ParseUint(totalFlakyFailuresStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to convert total_flaky_failures value to uint64").Err()
		}

		totalTriesStr, ok := row.F[3].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for total_tries column")
		}

		totalTries, err := strconv.ParseUint(totalTriesStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to convert total_tries value to uint64").Err()
		}

		flakinessStr, ok := row.F[4].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for string column")
		}

		flakiness, err := strconv.ParseFloat(flakinessStr, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to convert flakiness value to float64").Err()
		}

		cqFalseRejectionsStr, ok := row.F[5].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for cq_false_rejections column")
		}

		cqFalseRejections, err := strconv.ParseUint(cqFalseRejectionsStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to convert cq_false_rejections value to uint64").Err()
		}

		data = append(data, FlakinessListItem{
			TestName:           name,
			NormalizedStepName: normalizedStepName,
			Flakiness:          flakiness,
			TotalTries:         totalTries,
			TotalFlakyFailures: totalFlakyFailures,
			CQFalseRejections:  cqFalseRejections,
		})
	}

	return data, nil
}

func getBuildURL(s testFlakinessService, master, builder string, buildNumber uint64) string {
	return fmt.Sprintf(
		"https://luci-milo.appspot.com/buildbot/%s/%s/%d",
		strings.TrimPrefix(master, "master."), builder, buildNumber)
}

func findStep(step *milo.Step, stepName string) *milo.Step {
	if step.Name == stepName {
		return step
	}

	for _, substep := range step.Substep {
		if cs := substep.GetStep(); cs != nil {
			if detectedStep := findStep(cs, stepName); detectedStep != nil {
				return detectedStep
			}
		}
	}

	return nil
}

func getStdoutLogURL(ctx context.Context, s testFlakinessService, master, builder string, buildNumber uint64, stepName string) (string, error) {
	buildInfoClient, err := s.GetBuildInfoClient(ctx)
	if err != nil {
		return "", err
	}

	resp, err := buildInfoClient.Get(ctx, &milo_api.BuildInfoRequest{
		Build: &milo_api.BuildInfoRequest_Buildbot{
			Buildbot: &milo_api.BuildInfoRequest_BuildBot{
				MasterName:  strings.TrimPrefix(master, "master."),
				BuilderName: builder,
				BuildNumber: int64(buildNumber),
			},
		},
	})
	if err != nil {
		logging.WithError(err).Errorf(ctx, "Failed to retrieve BuildInfo for a build")
		return "", err
	}

	step := findStep(resp.Step, stepName)
	if step == nil {
		return "", errors.Reason("failed to find step %(step)q").D("step", stepName).Err()
	}

	stream := step.StdoutStream
	if resp.AnnotationStream != nil {
		if stream.Server == "" {
			stream.Server = resp.AnnotationStream.Server
		}
		if stream.Prefix == "" {
			stream.Prefix = resp.AnnotationStream.Prefix
		}
	}

	if stream.Server == "" || resp.Project == "" || stream.Prefix == "" || stream.Name == "" {
		return "", errors.New("missing pieces needed to get log stream URL")
	}

	return viewer.GetURL(
		stream.Server,
		cfgtypes.ProjectName(resp.Project),
		types.StreamName(stream.Prefix).Join(types.StreamName(stream.Name)),
	), nil
}

func getFlakyBuildsForTest(ctx context.Context, s testFlakinessService, mr parallel.MultiRunner, bq *bigquery.Service, test string) ([]FlakyBuild, error) {
	queryParams := []*bigquery.QueryParameter{
		{
			Name:           "testname",
			ParameterType:  &bigquery.QueryParameterType{Type: "STRING"},
			ParameterValue: &bigquery.QueryParameterValue{Value: test},
		},
	}

	rows, err := executeBQQuery(ctx, bq, flakyBuildsQuery, queryParams)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	flakyBuilds := make([]FlakyBuild, len(rows))
	err = mr.RunMulti(func(taskC chan<- func() error) {
		for idx, row := range rows {
			idx, row := idx, row
			taskC <- func() (err error) {
				master, ok := row.F[0].V.(string)
				if !ok {
					return errors.New("query returned non-string master column")
				}

				builder, ok := row.F[1].V.(string)
				if !ok {
					return errors.New("query returned non-string builder column")
				}

				buildNumberStr, ok := row.F[2].V.(string)
				if !ok {
					return errors.New("query returned non-string build_number column")
				}

				buildNumber, err := strconv.ParseUint(buildNumberStr, 10, 64)
				if err != nil {
					return errors.Annotate(err).Reason("failed to convert build_number value to int64").Err()
				}

				stepName, ok := row.F[3].V.(string)
				if !ok {
					return errors.New("query returned non-string step_name column")
				}

				var logURL string
				if logURL, err = getStdoutLogURL(ctx, s, master, builder, buildNumber, stepName); err != nil {
					return err
				}

				flakyBuilds[idx] = FlakyBuild{
					BuildURL: getBuildURL(s, master, builder, buildNumber),
					LogURL:   logURL,
				}
				return nil
			}
		}
	})

	return flakyBuilds, err
}

func getCQFalseRejectionBuildsForTest(ctx context.Context, s testFlakinessService, mr parallel.MultiRunner, bq *bigquery.Service, test string) ([]CQFlakyBuild, error) {
	queryParams := []*bigquery.QueryParameter{
		{
			Name:           "testname",
			ParameterType:  &bigquery.QueryParameterType{Type: "STRING"},
			ParameterValue: &bigquery.QueryParameterValue{Value: test},
		},
	}

	rows, err := executeBQQuery(ctx, bq, cqFlakyBuildsQuery, queryParams)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	cqFlakyBuilds := make([]CQFlakyBuild, len(rows))
	err = mr.RunMulti(func(taskC chan<- func() error) {
		for idx, row := range rows {
			idx, row := idx, row
			taskC <- func() (err error) {
				master, ok := row.F[0].V.(string)
				if !ok {
					return errors.New("query returned non-string master column")
				}

				builder, ok := row.F[1].V.(string)
				if !ok {
					return errors.New("query returned non-string builder column")
				}

				passedBuildNumberStr, ok := row.F[2].V.(string)
				if !ok {
					return errors.New("query returned non-string passed_build_number column")
				}

				passedBuildNumber, err := strconv.ParseUint(passedBuildNumberStr, 10, 64)
				if err != nil {
					return errors.Annotate(err).Reason("failed to convert passed_build_number value to int64").Err()
				}

				failedBuildNumberStr, ok := row.F[3].V.(string)
				if !ok {
					return errors.New("query returned non-string failed_build_number column")
				}

				failedBuildNumber, err := strconv.ParseUint(failedBuildNumberStr, 10, 64)
				if err != nil {
					return errors.Annotate(err).Reason("failed to convert failed_build_number value to int64").Err()
				}

				stepName, ok := row.F[4].V.(string)
				if !ok {
					return errors.New("query returned non-string step_name column")
				}

				var passedLogURL, failedLogURL string
				err = parallel.FanOutIn(func(taskC chan<- func() error) {
					taskC <- func() (err error) {
						passedLogURL, err = getStdoutLogURL(ctx, s, master, builder, passedBuildNumber, stepName)
						return err
					}

					taskC <- func() (err error) {
						failedLogURL, err = getStdoutLogURL(ctx, s, master, builder, failedBuildNumber, stepName)
						return err
					}
				})

				if err != nil {
					return err
				}

				cqFlakyBuilds[idx] = CQFlakyBuild{
					PassedBuildURL: getBuildURL(s, master, builder, passedBuildNumber),
					PassedLogURL:   passedLogURL,
					FailedBuildURL: getBuildURL(s, master, builder, failedBuildNumber),
					FailedLogURL:   failedLogURL,
				}
				return nil
			}
		}
	})

	return cqFlakyBuilds, err
}

func getFlakinessData(aeCtx context.Context, s testFlakinessService, bq *bigquery.Service, test string) (*FlakyTestDetails, error) {
	var flakyBuilds []FlakyBuild
	var cqFlakyBuilds []CQFlakyBuild
	err := parallel.RunMulti(aeCtx, 50, func(mr parallel.MultiRunner) error {
		return mr.RunMulti(func(taskC chan<- func() error) {
			taskC <- func() (err error) {
				flakyBuilds, err = getFlakyBuildsForTest(aeCtx, s, mr, bq, test)
				return
			}

			taskC <- func() (err error) {
				cqFlakyBuilds, err = getCQFalseRejectionBuildsForTest(aeCtx, s, mr, bq, test)
				return
			}
		})
	})

	return &FlakyTestDetails{
		FlakyBuilds:   flakyBuilds,
		CQFlakyBuilds: cqFlakyBuilds,
	}, err
}

type testFlakinessService interface {
	GetBuildInfoClient(context.Context) (milo_api.BuildInfoClient, error)
	GetBQService(aeCtx context.Context) (*bigquery.Service, error)
}

type prodTestFlakinessService struct{}

func (p prodTestFlakinessService) GetBuildInfoClient(ctx context.Context) (milo_api.BuildInfoClient, error) {
	authTransport, err := auth.GetRPCTransport(ctx, auth.AsUser)
	if err != nil {
		return nil, err
	}

	options := prpc.DefaultOptions()
	return milo_api.NewBuildInfoPRPCClient(&prpc.Client{
		Host:    "luci-milo.appspot.com",
		C:       &http.Client{Transport: authTransport},
		Options: options,
	}), nil
}

func (p prodTestFlakinessService) GetBQService(aeCtx context.Context) (*bigquery.Service, error) {
	hc, err := google.DefaultClient(aeCtx, bigquery.BigqueryScope)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create http client").Err()
	}

	bq, err := bigquery.New(hc)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create service object").Err()
	}

	return bq, nil
}

func testFlakinessDataHandler(ctx *router.Context) {
	test := ctx.Request.FormValue("test")

	if test == "" {
		writeError(ctx, nil, "testFlakinessDataHandler", "missing test parameter")
		return
	}

	ctx.Context = appengine.WithContext(ctx.Context, ctx.Request)
	cachedDataHandler(
		ctx,
		prodTestFlakinessService{},
		"testFlakinessDataHandler",
		fmt.Sprintf(flakinessDataKeyTemplate, test),
		new(FlakyTestDetails),
		func(aeCtx context.Context, s testFlakinessService, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessData(aeCtx, s, bq, test)
		},
	)
}

func cachedDataHandler(ctx *router.Context, s testFlakinessService, funcName string, key string, data interface{}, fetchData func(aeCtx context.Context, s testFlakinessService, bq *bigquery.Service) (interface{}, error)) {
	// Check if we have recent results in memcache.
	memcacheItem, err := memcache.GetKey(ctx.Context, key)
	if err == nil {
		if err = json.Unmarshal(memcacheItem.Value(), &data); err != nil {
			logging.Fields{logging.ErrorKey: err, "item": memcacheItem}.Warningf(
				ctx.Context, "Failed to unmarshal cached results as JSON")
		} else {
			writeResponse(ctx, funcName, data)
			return
		}
	}

	bq, err := s.GetBQService(ctx.Context)
	if err != nil {
		writeError(ctx, err, funcName, "failed create BigQuery client")
		return
	}

	data, err = fetchData(ctx.Context, s, bq)
	if err != nil {
		writeError(ctx, err, funcName, "failed to get flakiness data")
		return
	}

	// Store results in memcache for 1 hour.
	if dataStr, err := json.Marshal(data); err == nil {
		memcacheItem.SetValue(dataStr).SetExpiration(time.Hour)
		if err = memcache.Set(ctx.Context, memcacheItem); err != nil {
			logging.WithError(err).Warningf(
				ctx.Context, "Failed to store query results in memcache")
		}
	} else {
		logging.WithError(err).Warningf(
			ctx.Context, "Failed to marshal query results as JSON: %#v", data)
	}

	writeResponse(ctx, funcName, data)
}

func testFlakinessListHandler(ctx *router.Context) {
	name := ctx.Request.FormValue("groupName")
	kind := ctx.Request.FormValue("groupKind")

	if kind == "" {
		writeError(ctx, nil, "testFlakinessListHandler", "missing groupKind parameter")
		return
	}

	if name == "" {
		writeError(ctx, nil, "testFlakinessListHandler", "missing groupName parameter")
		return
	}

	ctx.Context = appengine.WithContext(ctx.Context, ctx.Request)
	cachedDataHandler(
		ctx,
		prodTestFlakinessService{},
		"testFlakinessListHandler",
		fmt.Sprintf(flakinessListKeyTemplate, kind, name),
		new([]FlakinessListItem),
		func(aeCtx context.Context, s testFlakinessService, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessList(aeCtx, bq, Group{Name: name, Kind: kind})
		},
	)
}

var retryFactory = retry.Default

func executeBQQuery(ctx context.Context, bq *bigquery.Service, query string, params []*bigquery.QueryParameter) ([]*bigquery.TableRow, error) {
	logging.Debugf(ctx, "Executing query `%s` with params `%#v`", query, params)

	bqProjectID := info.AppID(ctx)
	useLegacySQL := false
	request := bq.Jobs.Query(bqProjectID, &bigquery.QueryRequest{
		TimeoutMs:       bqQueryTimeout,
		Query:           query,
		UseLegacySql:    &useLegacySQL,
		QueryParameters: params,
	}).Context(ctx)

	var response *bigquery.QueryResponse
	err := retry.Retry(ctx, retryFactory, func() error {
		var err error
		response, err = request.Do()
		return err
	}, nil)

	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	// Check if BQ has returned results or wait for them in a loop. Unfortunately
	// we are not able to just use high BigQuery timeout since HTTP(S) requests on
	// AppEngine are limited to 60 seconds.
	var rows []*bigquery.TableRow
	var pageToken string
	jobID := response.JobReference.JobId
	if response.JobComplete {
		// Query returned results immediately.
		rows = make([]*bigquery.TableRow, 0, response.TotalRows)
		rows = append(rows, response.Rows...)
		pageToken = response.PageToken
	} else {
		// Query is still running. Wait for results. We do not put a timeout for
		// this loop since AppEngine will terminate ourselves automatically after
		// overall request timeout is reached.
		for {
			resultsRequest := bq.Jobs.GetQueryResults(bqProjectID, jobID)
			resultsRequest.TimeoutMs(bqQueryTimeout)
			var resultsResponse *bigquery.GetQueryResultsResponse
			err := retry.Retry(ctx, retry.Default, func() error {
				var err error
				resultsResponse, err = resultsRequest.Do()
				return err
			}, nil)
			if err != nil {
				return nil, errors.Annotate(err).Reason("failed to retrieve results").Err()
			}
			if resultsResponse.JobComplete {
				rows = make([]*bigquery.TableRow, 0, resultsResponse.TotalRows)
				rows = append(rows, resultsResponse.Rows...)
				pageToken = resultsResponse.PageToken
				break
			}
		}
	}

	// Get additional results if any.
	for pageToken != "" {
		resultsRequest := bq.Jobs.GetQueryResults(bqProjectID, jobID)
		resultsRequest.PageToken(pageToken)
		var resultsResponse *bigquery.GetQueryResultsResponse
		err := retry.Retry(ctx, retry.Default, func() error {
			var err error
			resultsResponse, err = resultsRequest.Do()
			return err
		}, nil)

		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to retrive additional results").Err()
		}

		rows = append(rows, resultsResponse.Rows...)
		pageToken = resultsResponse.PageToken
	}

	logging.Debugf(ctx, "Received %d results", len(rows))
	return rows, nil
}

func getGroupsForQuery(ctx context.Context, bq *bigquery.Service, query, kind, nilKind string) ([]Group, error) {
	rows, err := executeBQQuery(ctx, bq, query, nil)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	var groups []Group
	for _, row := range rows {
		value := row.F[0].V
		switch value := value.(type) {
		case string:
			groups = append(groups, Group{Name: value, Kind: kind})
		case nil:
			if nilKind == "" {
				return nil, errors.New("unexpected NULL value for a group")
			}
			groups = append(groups, Group{Name: nilKind, Kind: nilKind})
		default:
			return nil, errors.New("query returned non-string non-nil value")
		}
	}

	return groups, nil
}

func getFlakinessGroups(ctx context.Context, bq *bigquery.Service) ([]Group, error) {
	var teamGroups, dirGroups, suiteGroups []Group
	err := parallel.FanOutIn(func(taskC chan<- func() error) {
		taskC <- func() (err error) {
			teamGroups, err = getGroupsForQuery(ctx, bq, teamsQuery, TeamKind, UnknownTeamKind)
			return
		}

		taskC <- func() (err error) {
			dirGroups, err = getGroupsForQuery(ctx, bq, dirsQuery, DirKind, UnknownDirKind)
			return
		}

		taskC <- func() (err error) {
			suiteGroups, err = getGroupsForQuery(ctx, bq, suitesQuery, TestSuiteKind, "")
			return
		}
	})

	groups := make([]Group, 0, len(teamGroups)+len(dirGroups)+len(suiteGroups))
	return append(append(append(groups, teamGroups...), dirGroups...), suiteGroups...), err
}

func testFlakinessGroupsHandler(ctx *router.Context) {
	ctx.Context = appengine.WithContext(ctx.Context, ctx.Request)
	cachedDataHandler(
		ctx,
		prodTestFlakinessService{},
		"testFlakinessGroupsHandler",
		flakinessGroupsKey,
		new([]Group),
		func(aeCtx context.Context, s testFlakinessService, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessGroups(aeCtx, bq)
		},
	)
}
