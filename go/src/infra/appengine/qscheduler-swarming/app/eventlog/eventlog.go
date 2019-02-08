// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package eventlog

import (
	"context"

	"cloud.google.com/go/bigquery"
	"go.chromium.org/luci/appengine/bqlog"
	"go.chromium.org/luci/common/bq"

	"infra/qscheduler/qslib/metrics"
)

// tasks is the BigQuery logger for metrics.TaskEvent entries.
var tasks = &bqlog.Log{
	QueueName: "flush-events",
	DatasetID: "qs_events",
	TableID:   "task_events",
}

// TaskEvents logs the given TaskEvents to a bigquery table, on a separate
// taskqueue call (and is aware of datastore transactions).
func TaskEvents(ctx context.Context, events ...*metrics.TaskEvent) error {
	rows := make([]bigquery.ValueSaver, len(events))
	for i, v := range events {
		rows[i] = &bq.Row{Message: v}
	}
	return tasks.Insert(ctx, rows...)
}

// FlushEvents flushes task events to bigquery. This is called by cron.
func FlushEvents(ctx context.Context) error {
	_, err := tasks.Flush(ctx)
	return err
}
