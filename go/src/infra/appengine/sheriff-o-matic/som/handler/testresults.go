// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handler

import (
	"fmt"
	"net/http"
	"time"

	"golang.org/x/net/context"

	"google.golang.org/api/iterator"
	"google.golang.org/api/option"

	"infra/monitoring/messages"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"cloud.google.com/go/bigquery"
)

const scope = "https://www.googleapis.com/auth/bigquery"
const testResultsQuery = `
  SELECT
    build_number,
    t.actual,
    t.expected,
    master_name,
    builder_name,
    t.test_name
  FROM
    plx.google.chrome_infra.test_results.last%ddays, UNNEST(tests) AS t
  WHERE
    master_name = @master
  AND
    builder_name = @builder
  AND
    step_name = @step
  AND
    t.test_name = @testname
  ORDER BY
    usec_since_epoch DESC
  LIMIT 30
`

type bqIterator interface {
	Next(interface{}) error
}

// getBuildersByMaster builds a map with master name keys and a list of builder names
// for each value.
//
// It returns the map and takes a slice of AlertedBuilders that need to be sorted based on their masters.
func getBuildersByMaster(builders []messages.AlertedBuilder) map[string][]string {
	buildersByMaster := map[string][]string{}
	for _, builder := range builders {
		buildersByMaster[builder.Master] = append(buildersByMaster[builder.Master], builder.Name)
	}
	return buildersByMaster
}

// isTestFaillure returns true/false based on whether the given Alert is for BuildFailure.
func isTestFailure(alert messages.Alert) bool {
	if bf, ok := alert.Extension.(messages.BuildFailure); ok && bf.Reason.Kind() == "test" {
		return true
	}
	return false
}

// getBQClient returns a bigquery Client for accessing bigquery tables.
// on error it return (nil, err)
func getBQClient(c context.Context) (*bigquery.Client, error) {
	authTransport, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		logging.Errorf(c, "error getting rpc transport: %v", err)
		return nil, err
	}
	httpClient := &http.Client{Transport: authTransport}
	client, err := bigquery.NewClient(c, "sheriff-o-matic", option.WithScopes(scope), option.WithHTTPClient(httpClient))
	if err != nil {
		logging.Errorf(c, "err geting bigquery Client: %v", err)
		return nil, err
	}
	return client, nil
}

// getTestResultsQuery formats and returns a query string for bigquery, using
// the given arguments to customize the testResultsQuery template.
func getTestResultsQuery(startTime time.Time) string {
	diff := time.Now().Sub(startTime)
	daysAgo := int(diff.Hours() / 24)
	return fmt.Sprintf(testResultsQuery, daysAgo)
}

// makeQueryParameters builds and returns an array of bigqueryQuery Parameters
func makeQueryParameters(testName, masterName, builderName, stepName string) []bigquery.QueryParameter {
	return []bigquery.QueryParameter{
		{Name: "master", Value: masterName},
		{Name: "builder", Value: builderName},
		{Name: "step", Value: stepName},
		{Name: "testname", Value: testName},
	}
}

// getTestResults builds, executes, and reads a bigquery query. The query result's rows are used
// to populate a slice of messages.Results
//
// On success it returns (messages.Results, nil) on error it returns (nil, err)
func getTestResults(ctx *router.Context, bqClient *bigquery.Client, startTime time.Time, test, master, builder, step string) ([]messages.Results, error) {
	c := ctx.Context

	// create query
	queryString := getTestResultsQuery(startTime)
	query := bqClient.Query(queryString)
	query.Parameters = makeQueryParameters(test, master, builder, step)

	// execute query and read results
	it, err := query.Read(c)
	if err != nil {
		logging.Errorf(c, "error executing bigquery query: %v", err)
		return nil, err
	}
	return extractResults(c, it)
}

func extractResults(c context.Context, it bqIterator) ([]messages.Results, error) {
	allResults := make([]messages.Results, 0, 30)
	for {
		var result messages.Results
		err := it.Next(&result)
		if err == iterator.Done {
			break
		}
		if err != nil {
			logging.Errorf(c, "error reading next bigquery row: %v", err)
			return nil, err
		}
		allResults = append(allResults, result)
	}
	return allResults, nil
}
