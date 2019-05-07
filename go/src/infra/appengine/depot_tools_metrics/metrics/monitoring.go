// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package metrics stores the reported JSON metrics from depot_tools into a
// BigQuery table.
package metrics

import (
	"go.chromium.org/luci/common/data/stringset"
	"go.chromium.org/luci/common/tsmon/distribution"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
	"golang.org/x/net/context"
	"infra/appengine/depot_tools_metrics/schema"
)

// chromiumSrc is the URL of the chromium/src repo. It is counted apart from all
// the other repos.
const chromiumSrc = "https://chromium.googlesource.com/chromium/src"

var (
	// GitPushLatency keeps track of how long it takes to run git push per repo.
	GitPushLatency = metric.NewCumulativeDistribution(
		"depot_tools_metrics/git_push_latency",
		"Time it takes to run git push.",
		&types.MetricMetadata{Units: types.Milliseconds},
		distribution.DefaultBucketer,
		field.Int("exit_code"),
		field.String("repo"),
	)
)

// reportGitPushMetrics reports git push metrics to ts_mon.
func reportGitPushMetrics(ctx context.Context, m schema.Metrics) {
	if len(m.ProjectUrls) == 0 {
		return
	}
	if len(m.SubCommands) == 0 {
		return
	}
	repo := "everything_else"
	if stringset.NewFromSlice(m.ProjectUrls...).Has(chromiumSrc) {
		repo = chromiumSrc
	}
	for _, sc := range m.SubCommands {
		if sc.Command != "git push" {
			continue
		}
		GitPushLatency.Add(ctx, sc.ExecutionTime, sc.ExitCode, repo)
	}
}
