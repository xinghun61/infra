// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"go.chromium.org/luci/appengine/bqlog"
)

// Below are bqlog.Log definitions; for each Log there should be a separate
// queue. The queue must be listed in queue.yaml, and the dataset and table
// should match that in setup_bigquery.sh.

// ResultsLog includes rows with analyzer results created when an analysis
// workflow is complete.
var ResultsLog = bqlog.Log{
	QueueName: AnalysisResultsQueue,
	DatasetID: "analyzer",
	TableID:   "results",
}

// EventsLog includes rows for events, such as "not useful" clicks and sending
// of comments.
var EventsLog = bqlog.Log{
	QueueName: FeedbackEventsQueue,
	DatasetID: "events",
	TableID:   "feedback",
}
