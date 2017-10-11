// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package tracker

import (
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
)

var (
	workerSuccessCount = metric.NewCounter("tricium/worker/success",
		"Number of successful workers",
		nil,
		field.String("analyzer"),
		field.String("platform"))

	workerFailureCount = metric.NewCounter("tricium/worker/failure",
		"Number of failing workers",
		nil,
		field.String("analyzer"),
		field.String("platform"),
		field.String("failure"))

	commentCount = metric.NewCounter("tricium/analyzer/comment_count",
		"Number of comments generated",
		nil,
		field.String("analyzer"),
		field.String("platform"))
)
