// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"go.chromium.org/luci/appengine/bqlog"
)

// ResultsLog includes rows with analyzer results created when an analysis
// workflow is complete.
var ResultsLog = bqlog.Log{
	QueueName: AnalysisResultsQueue, // Must be listed in queue.yaml.
	DatasetID: "analyzer",           // Must match setup_bigquery.sh.
	TableID:   "results",            // Must match setup_bigquery.sh.
}
