// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	analyzeRequestCount = metric.NewCounter("tricium/request/analyze_count",
		"Number of analyze requests",
		nil,
		field.String("project"))

	progressRequestCount = metric.NewCounter("tricium/request/progress_count",
		"Number of progress requests",
		nil,
		field.String("project"),
		field.String("run_id"))

	resultsRequestCount = metric.NewCounter("tricium/request/results_count",
		"Number of results requests",
		nil,
		field.String("project"),
		field.String("run_id"))
)
