// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"

	"google.golang.org/appengine"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/server/router"
	"golang.org/x/net/context"
	"golang.org/x/oauth2/google"
	"golang.org/x/sync/errgroup"
	bigquery "google.golang.org/api/bigquery/v2"
)

const teamsQuery = `
	SELECT layout_test_team
	FROM plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
	GROUP BY layout_test_team;`

const dirsQuery = `
	SELECT layout_test_dir
	FROM plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
	GROUP BY layout_test_dir;`

const flakesQuery = `
	SELECT test_name, flakiness
	FROM plx.google.chrome_infra.flaky_tests_with_layout_team_dir_info.all
	WHERE %s
	ORDER BY flakiness DESC
	LIMIT 1000;
`

const bqProjectID = "test-results-hrd"

// Flakiness represents infromation about a single flaky test.
type Flakiness struct {
	TestName        string  `json:"test_name"`
	Flakiness       float64 `json:"flakiness"`
	FalseRejections uint    `json:"false_rejections"`
}

// Group represents infromation about flakiness of a group of tests.
type Group struct {
	Name string `json:"name"`
	Kind string `json:"kind"`
}

func writeError(ctx *router.Context, err error, funcName string, msg string) {
	if err != nil {
		logging.WithError(err).Errorf(ctx.Context, "%s: %s", funcName, msg)
	} else {
		logging.Errorf(ctx.Context, "%s: %s", funcName, msg)
	}

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

func getFlakinessData(ctx context.Context, bq *bigquery.Service, group Group) ([]Flakiness, error) {
	var filter string
	switch group.Kind {
	case "team":
		// TODO(sergiyb): Change this when we have a way to detect which team owns a
		// given test (other than layout test).
		filter = "layout_test_team = @groupname"
	case "dir":
		filter = "layout_test_dir = @groupname"
	case "unknown-team":
		filter = "layout_test_team is None"
	case "unknown-dir":
		filter = "layout_test_dir is None"
	case "test-suite":
		filter = "STARTS_WITH(test_name, @groupname + '.')"
	case "substring":
		filter = "STRPOS(test_name, @groupname) != 0"
	default:
		return nil, errors.New("unknown group kind")
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

	data := make([]Flakiness, 0, len(rows))
	for _, row := range rows {
		name, ok := row.F[0].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string test name column")
		}

		flakinessStr, ok := row.F[1].V.(string)
		if !ok {
			return nil, errors.New("query returned non-string value for flakiness column")
		}

		flakiness, err := strconv.ParseFloat(flakinessStr, 64)
		if err != nil {
			return nil, errors.Annotate(err).Reason("Failed to convert flakiness value to float").Err()
		}

		// TODO(sergiyb): Add number of false rejections per test.
		data = append(data, Flakiness{TestName: name, Flakiness: flakiness})
	}

	return data, nil
}

func testFlakinessHandler(ctx *router.Context) {
	// TODO(sergiyb): Add a layer of caching results using memcache.
	name := ctx.Request.FormValue("groupName")
	kind := ctx.Request.FormValue("groupKind")

	if kind == "" {
		writeError(ctx, nil, "testFlakinessHandler", "missing groupKind parameter")
		return
	}

	if kind != "unknown-dir" && kind != "unknown-team" && name == "" {
		writeError(ctx, nil, "testFlakinessHandler", "missing groupName parameter")
		return
	}

	bq, err := createBQService(appengine.NewContext(ctx.Request))
	if err != nil {
		writeError(ctx, err, "testFlakinessHandler", "failed create BigQuery client")
		return
	}

	data, err := getFlakinessData(ctx.Context, bq, Group{Name: name, Kind: kind})
	if err != nil {
		writeError(ctx, err, "testFlakinessHandler", "failed to get flakiness data")
		return
	}

	writeResponse(ctx, "testFlakinessHandler", data)
}

func createBQService(AECtx context.Context) (*bigquery.Service, error) {
	hc, err := google.DefaultClient(AECtx, bigquery.BigqueryScope)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create http client").Err()
	}

	bq, err := bigquery.New(hc)
	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to create service object").Err()
	}

	return bq, nil
}

func executeBQQuery(ctx context.Context, bq *bigquery.Service, query string, params []*bigquery.QueryParameter) ([]*bigquery.TableRow, error) {
	useLegacySQL := false
	request := bq.Jobs.Query(bqProjectID, &bigquery.QueryRequest{
		Query:           query,
		TimeoutMs:       5000,
		UseLegacySql:    &useLegacySQL,
		QueryParameters: params,
	})

	var response *bigquery.QueryResponse
	err := retry.Retry(ctx, retry.Default, func() error {
		var err error
		response, err = request.Do()
		return err
	}, nil)

	if err != nil {
		return nil, errors.Annotate(err).Reason("failed to execute query").Err()
	}

	rows := make([]*bigquery.TableRow, 0, response.TotalRows)
	// TODO(sergiyb): BigQuery may set JobComplete to false and not populate Rows
	// array. We need to handle this correctly and use GetQueryResults to actually
	// get results when the query is complete.
	rows = append(rows, response.Rows...)
	jobID := response.JobReference.JobId
	pageToken := response.PageToken
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
			groups = append(groups, Group{Kind: nilKind})
		default:
			return nil, errors.New("query returned non-string non-nil value")
		}
	}

	return groups, nil
}

func getFlakinessGroups(ctx context.Context, bq *bigquery.Service) ([]Group, error) {
	var teamGroups, dirGroups []Group
	var g errgroup.Group

	g.Go(func() (err error) {
		teamGroups, err = getGroupsForQuery(ctx, bq, teamsQuery, "team", "unknown-team")
		return
	})

	g.Go(func() (err error) {
		dirGroups, err = getGroupsForQuery(ctx, bq, dirsQuery, "dir", "unknown-dir")
		return
	})

	if err := g.Wait(); err != nil {
		return nil, err
	}

	return append(teamGroups, dirGroups...), nil
}

func testFlakinessGroupsHandler(ctx *router.Context) {
	// TODO(sergiyb): Add a layer of caching results using memcache.
	bq, err := createBQService(ctx.Context)
	if err != nil {
		writeError(ctx, err, "testFlakinessGroupsHandler", "failed create BigQuery client")
		return
	}

	groups, err := getFlakinessGroups(ctx.Context, bq)
	if err != nil {
		writeError(ctx, err, "testFlakinessGroupsHandler", "failed to get flakiness groups")
		return
	}

	writeResponse(ctx, "testFlakinessGroupsHandler", groups)
}
