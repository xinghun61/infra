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
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"
	"golang.org/x/oauth2/google"
	"golang.org/x/sync/errgroup"
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
    test_name = @testname;`

// TODO(sergiyb): Implement query.
const falseRejectionBuildsQuery = `
  SELECT
    'not-implemented' as master,
    'not-implemented' as builder,
    'not-implemented' as passed_build_number,
    'not-implemented' as failed_build_number,
    'not-implemented' as step_name;`

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
	CQFalseRejections  uint64  `json:"cq_false_rejections"`
}

// FlakyBuild represents a build in which a test has passed and failed.
type FlakyBuild struct {
	BuildURL string `json:"build_url"`
	LogURL   string `json:"log_url"`
}

// FalseRejectionBuild represent a build, which has failed due to a flaky test.
type FalseRejectionBuild struct {
	PassedBuildURL string `json:"passed_build_url"`
	PassedLogURL   string `json:"passed_log_url"`
	FailedBuildURL string `json:"failed_build_url"`
	FailedLogURL   string `json:"failed_log_url"`
}

// FlakyTestDetails represents detailed information about a flaky test.
type FlakyTestDetails struct {
	FlakyBuilds          []FlakyBuild          `json:"flaky_builds"`
	FalseRejectionBuilds []FalseRejectionBuild `json:"false_rejection_builds"`
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
			return nil, errors.Annotate(err).Reason("Failed to convert total_flaky_failures value to uint64").Err()
		}

		totalTriesStr, ok := row.F[3].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for total_tries column")
		}

		totalTries, err := strconv.ParseUint(totalTriesStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert total_tries value to uint64").Err()
		}

		flakinessStr, ok := row.F[4].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for string column")
		}

		flakiness, err := strconv.ParseFloat(flakinessStr, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert flakiness value to float64").Err()
		}

		cqFalseRejectionsStr, ok := row.F[5].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for cq_false_rejections column")
		}

		cqFalseRejections, err := strconv.ParseUint(cqFalseRejectionsStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert cq_false_rejections value to uint64").Err()
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

func getBuildURL(master, builder string, buildNumber uint64) string {
	return fmt.Sprintf(
		"https://build.chromium.org/p/%s/builders/%s/builds/%d",
		strings.TrimPrefix(master, "master."), builder, buildNumber)
}

func getStdoutLogURL(master, builder string, buildNumber uint64, stepName string) string {
	// TODO(sergiyb): Query list of logs for a build from Milo using pRPC endpoint
	// https://luci-milo.appspot.com/rpcexplorer/services/milo.BuildInfo/Get and
	// format logdog URL for the matching step using GetURL function from package
	// luci/luci-go/logdog/common/viewer.
	return "not-implemented"
}

func getFlakyBuildsForTest(ctx context.Context, bq *bigquery.Service, test string) ([]FlakyBuild, error) {
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

	flakyBuilds := make([]FlakyBuild, 0, len(rows))
	for _, row := range rows {
		master, ok := row.F[0].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string master column")
		}

		builder, ok := row.F[1].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string builder column")
		}

		buildNumberStr, ok := row.F[2].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string build_number column")
		}

		buildNumber, err := strconv.ParseUint(buildNumberStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert build_number value to uint64").Err()
		}

		stepName, ok := row.F[3].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string step_name column")
		}

		flakyBuilds = append(flakyBuilds, FlakyBuild{
			BuildURL: getBuildURL(master, builder, buildNumber),
			LogURL:   getStdoutLogURL(master, builder, buildNumber, stepName),
		})
	}

	return flakyBuilds, nil
}

func getCQFalseRejectionBuildsForTest(ctx context.Context, bq *bigquery.Service, test string) ([]FalseRejectionBuild, error) {
	queryParams := []*bigquery.QueryParameter{
		{
			Name:           "testname",
			ParameterType:  &bigquery.QueryParameterType{Type: "STRING"},
			ParameterValue: &bigquery.QueryParameterValue{Value: test},
		},
	}

	rows, err := executeBQQuery(ctx, bq, falseRejectionBuildsQuery, queryParams)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	falseRejectionBuilds := make([]FalseRejectionBuild, 0, len(rows))
	for _, row := range rows {
		master, ok := row.F[0].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string master column")
		}

		builder, ok := row.F[1].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string builder column")
		}

		passedBuildNumberStr, ok := row.F[2].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string passed_build_number column")
		}

		passedBuildNumber, err := strconv.ParseUint(passedBuildNumberStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert passed_build_number value to uint64").Err()
		}

		failedBuildNumberStr, ok := row.F[3].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string failed_build_number column")
		}

		failedBuildNumber, err := strconv.ParseUint(failedBuildNumberStr, 10, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert failed_build_number value to uint64").Err()
		}

		stepName, ok := row.F[4].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string step_name column")
		}

		falseRejectionBuilds = append(falseRejectionBuilds, FalseRejectionBuild{
			PassedBuildURL: getBuildURL(master, builder, passedBuildNumber),
			PassedLogURL:   getStdoutLogURL(master, builder, passedBuildNumber, stepName),
			FailedBuildURL: getBuildURL(master, builder, failedBuildNumber),
			FailedLogURL:   getStdoutLogURL(master, builder, failedBuildNumber, stepName),
		})
	}

	return falseRejectionBuilds, nil
}

func getFlakinessData(aeCtx context.Context, bq *bigquery.Service, test string) (*FlakyTestDetails, error) {
	var flakyBuilds []FlakyBuild
	var falseRejectionBuilds []FalseRejectionBuild
	var g errgroup.Group

	g.Go(func() (err error) {
		flakyBuilds, err = getFlakyBuildsForTest(aeCtx, bq, test)
		return
	})

	g.Go(func() (err error) {
		falseRejectionBuilds, err = getCQFalseRejectionBuildsForTest(aeCtx, bq, test)
		return
	})

	if err := g.Wait(); err != nil {
		return &FlakyTestDetails{}, err
	}

	return &FlakyTestDetails{
		FlakyBuilds:          flakyBuilds,
		FalseRejectionBuilds: falseRejectionBuilds,
	}, nil
}

func testFlakinessDataHandler(ctx *router.Context) {
	test := ctx.Request.FormValue("test")

	if test == "" {
		writeError(ctx, nil, "testFlakinessDataHandler", "missing test parameter")
		return
	}

	cachedDataHandler(
		ctx,
		"testFlakinessDataHandler",
		fmt.Sprintf(flakinessDataKeyTemplate, test),
		new(FlakyTestDetails),
		func(aeCtx context.Context, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessData(aeCtx, bq, test)
		},
	)
}

func cachedDataHandler(ctx *router.Context, funcName string, key string, data interface{}, fetchData func(aeCtx context.Context, bq *bigquery.Service) (interface{}, error)) {
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

	aeCtx := appengine.WithContext(ctx.Context, ctx.Request)
	bq, err := createBQService(aeCtx)
	if err != nil {
		writeError(ctx, err, funcName, "failed create BigQuery client")
		return
	}

	data, err = fetchData(aeCtx, bq)
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

	cachedDataHandler(
		ctx,
		"testFlakinessListHandler",
		fmt.Sprintf(flakinessListKeyTemplate, kind, name),
		new([]FlakinessListItem),
		func(aeCtx context.Context, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessList(aeCtx, bq, Group{Name: name, Kind: kind})
		},
	)
}

func createBQService(aeCtx context.Context) (*bigquery.Service, error) {
	hc, err := google.DefaultClient(aeCtx, bigquery.BigqueryScope)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create http client").Err()
	}

	hc.Timeout = time.Minute // Increase timeout for BigQuery HTTP requests
	bq, err := bigquery.New(hc)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create service object").Err()
	}

	return bq, nil
}

var retryFactory = retry.Default

func executeBQQuery(ctx context.Context, bq *bigquery.Service, query string, params []*bigquery.QueryParameter) ([]*bigquery.TableRow, error) {
	logging.Infof(ctx, "Executing query `%s` with params %#v", query, params)

	bqProjectID := info.AppID(ctx)
	useLegacySQL := false
	request := bq.Jobs.Query(bqProjectID, &bigquery.QueryRequest{
		TimeoutMs:       bqQueryTimeout,
		Query:           query,
		UseLegacySql:    &useLegacySQL,
		QueryParameters: params,
	})

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
				return nil, errors.New("Unexpected NULL value for a group")
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
	var g errgroup.Group

	g.Go(func() (err error) {
		teamGroups, err = getGroupsForQuery(ctx, bq, teamsQuery, TeamKind, UnknownTeamKind)
		return
	})

	g.Go(func() (err error) {
		dirGroups, err = getGroupsForQuery(ctx, bq, dirsQuery, DirKind, UnknownDirKind)
		return
	})

	g.Go(func() (err error) {
		suiteGroups, err = getGroupsForQuery(ctx, bq, suitesQuery, TestSuiteKind, "")
		return
	})

	if err := g.Wait(); err != nil {
		return nil, err
	}

	return append(teamGroups, append(dirGroups, suiteGroups...)...), nil
}

func testFlakinessGroupsHandler(ctx *router.Context) {
	cachedDataHandler(
		ctx,
		"testFlakinessGroupsHandler",
		flakinessGroupsKey,
		new([]Group),
		func(aeCtx context.Context, bq *bigquery.Service) (interface{}, error) {
			return getFlakinessGroups(aeCtx, bq)
		},
	)
}
