// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package crauditcommits implements cr-audit-commits.appspot.com services.
package crauditcommits

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/api/gerrit"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/cr-audit-commits/buildstatus"
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
	miloCheck,
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
			g, err := getGitilesClient(ctx)
			if err != nil {
				return err
			}
			base := "https://chromium.googlesource.com/chromium/src.git"
			branch := "master"
			_, err = g.Log(ctx, base, branch, 1)
			if err != nil {
				return err
			}
			return nil
		},
	}
	gerritCheck = SmokeTestCheck{
		Name: "Check gerrit connectivity",
		Check: func(ctx context.Context) error {

			httpClient, err := getAuthenticatedHTTPClient(ctx)
			if err != nil {
				return err
			}
			ge, err := gerrit.NewClient(httpClient, "https://chromium-review.googlesource.com/")
			if err != nil {
				return err
			}
			clNum := "630300"
			_, _, err = ge.ChangeQuery(ctx, gerrit.ChangeQueryRequest{Query: clNum})
			if err != nil {
				return err
			}
			return nil
		},
	}
	miloCheck = SmokeTestCheck{
		Name: "Check milo connectivity",
		Check: func(ctx context.Context) error {
			m, err := buildstatus.NewAuditMiloClient(ctx, auth.AsSelf)
			if err != nil {
				return err
			}
			buildURL := "https://luci-milo.appspot.com/buildbot/chromium.linux/Android%20Builder/86716"
			_, err = m.GetBuildInfo(ctx, buildURL)
			if err != nil {
				return err
			}
			return nil
		},
	}
)
