// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"

	"context"

	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/common/api/gitiles"
	gitilespb "go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/server/router"

	"infra/monorail"
)

// SmokeTestCheck associates the proper test function with a short description.
type SmokeTestCheck struct {
	Name  string
	Check func(context.Context) error
}

// AuditAppSmokeTests contains basic connectivity and sanity tests for the app.
var AuditAppSmokeTests = []SmokeTestCheck{
	gitilesCheck,
	gerritCheck,
	monorailCheck,
}

// SmokeTest is a handler that iterates over the list of tests, executes them
// and displays results as appropriate.
func SmokeTest(rc *router.Context) {
	ctx, resp := rc.Context, rc.Writer
	fmt.Fprintf(resp, "<h3>Smoke test results<h3><hr/><table>")

	nTests := len(AuditAppSmokeTests)
	nPass := 0
	for i, check := range AuditAppSmokeTests {
		err := check.Check(ctx)
		if err == nil {
			fmt.Fprintf(resp, "<tr><td>%d</td><td>%q</td><td><font color=\"green\"> OK </font></td></tr>",
				i+1, check.Name)
			nPass++
		} else {
			fmt.Fprintf(resp, "<tr><td>%d</td><td>%q</td><td><font color=\"red\">%s</font></td></tr>",
				i+1, check.Name, err.Error())

		}
	}

	fmt.Fprintf(resp, "</table><br/><h3>%d/%d PASS</h3>", nPass, nTests)
	if nPass != nTests {
		http.Error(resp, "Some tests failed", 500)
	}

}

var (
	gitilesCheck = SmokeTestCheck{
		Name: "Check gitiles connectivity",
		Check: func(ctx context.Context) error {
			httpClient, err := getAuthenticatedHTTPClient(ctx, gerritScope, emailScope)
			if err != nil {
				return err
			}
			g, err := gitiles.NewRESTClient(httpClient, "chromium.googlesource.com", true)
			if err != nil {
				return err
			}
			req := gitilespb.LogRequest{
				Project:    "chromium/src",
				Committish: "master",
				PageSize:   1,
			}
			_, err = g.Log(ctx, &req)
			if err != nil {
				return err
			}
			return nil
		},
	}
	gerritCheck = SmokeTestCheck{
		Name: "Check gerrit connectivity",
		Check: func(ctx context.Context) error {

			httpClient, err := getAuthenticatedHTTPClient(ctx, gerritScope)
			if err != nil {
				return err
			}
			ge, err := gerrit.NewClient(httpClient, "https://chromium-review.googlesource.com/")
			if err != nil {
				return err
			}
			clNum := "630300"
			_, _, err = ge.ChangeQuery(ctx, gerrit.ChangeQueryParams{Query: clNum})
			if err != nil {
				return err
			}
			return nil
		},
	}
	monorailCheck = SmokeTestCheck{
		Name: "Check monorail connectivity",
		Check: func(ctx context.Context) error {
			httpClient, err := getAuthenticatedHTTPClient(ctx, emailScope)
			if err != nil {
				return err
			}
			mu := "https://monorail-prod.appspot.com/_ah/api/monorail/v1"
			mrc := monorail.NewEndpointsClient(httpClient, mu)
			req := &monorail.IssuesListRequest{
				ProjectId: "chromium",
				Can:       monorail.IssuesListRequest_ALL,
				Q:         "753158",
			}
			resp, err := mrc.IssuesList(ctx, req)
			if err != nil {
				return err
			}
			if len(resp.Items) == 0 {
				return fmt.Errorf("No issue found with query \"753158\"")
			}
			return nil
		},
	}
)
