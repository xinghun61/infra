// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main stores the reported JSON metrics from depot_tools into a
// BigQuery table.
package main

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
	// GitLatency keeps track of how long it takes to run a git command per repo
	// and exit code.
	// We only keep track of the git commands executed by a depot_tools command.
	GitLatency = metric.NewCumulativeDistribution(
		"depot_tools_metrics/git/latency",
		"Time it takes to run a git command.",
		&types.MetricMetadata{Units: types.Seconds},
		// A growth factor if 1.045 with 200 buckets covers up to about 100m,
		// which is the interval we're interested about.
		distribution.GeometricBucketer(1.045, 200),
		field.String("command"),
		field.Int("exit_code"),
		field.String("repo"),
	)

	// GitExecutions counts the number of times a git command has been executed
	// per repo and exit code.
	// We only keep track of the git commands executed by a depot_tools command.
	GitExecutions = metric.NewCounter(
		"depot_tools_metrics/git/count",
		"Number of executions per git command.",
		nil,
		field.String("command"),
		field.Int("exit_code"),
		field.String("repo"),
	)

	// PresubmitLatency keeps track of how long it takes to run presubmit cheks
	// per repo and exit code.
	PresubmitLatency = metric.NewCumulativeDistribution(
		"depot_tools_metrics/presubmit",
		"Time it takes to run presubmit checks.",
		&types.MetricMetadata{Units: types.Seconds},
		// A growth factor if 1.03 with 200 buckets covers up to about 5m,
		// which is the interval we're interested about.
		distribution.GeometricBucketer(1.03, 200),
		field.Int("exit_code"),
		field.String("repo"),
	)
)

// reportDepotToolsMetrics reports metrics to ts_mon.
func reportDepotToolsMetrics(ctx context.Context, m schema.Metrics) {
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
		if sc.Command == "git push" {
			GitLatency.Add(ctx, sc.ExecutionTime, sc.Command, sc.ExitCode, repo)
			GitExecutions.Add(ctx, 1, sc.Command, sc.ExitCode, repo)
		}
		if sc.Command == "presubmit" {
			PresubmitLatency.Add(ctx, sc.ExecutionTime, sc.ExitCode, repo)
		}
	}
}
