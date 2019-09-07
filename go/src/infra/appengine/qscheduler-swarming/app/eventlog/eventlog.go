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
	"go.chromium.org/luci/common/bq"

	"infra/qscheduler/qslib/protos/metrics"
)

const (
	// DatasetID is name of BQ dataset.
	DatasetID = "qs_events"
	// TableID is name of BQ table.
	TableID = "task_events"
)

// TaskEvents logs the given TaskEvents to a bigquery table asynchronously.
func TaskEvents(ctx context.Context, events ...*metrics.TaskEvent) error {
	rows := make([]bigquery.ValueSaver, len(events))
	for i, v := range events {
		rows[i] = &bq.Row{Message: v}
	}
	return get(ctx).Insert(ctx, rows...)
}

// AsyncBqInserter defines what eventlog package expects from BQ inserting
// library.
type AsyncBqInserter interface {
	Insert(ctx context.Context, rows ...bigquery.ValueSaver) error
}

var contextKey = "eventlog"

// Use installs inserter into c.
func Use(c context.Context, inserter AsyncBqInserter) context.Context {
	return context.WithValue(c, &contextKey, inserter)
}

// get returns the BqInserter in c, or panics.
// See also Use.
func get(c context.Context) AsyncBqInserter {
	return c.Value(&contextKey).(AsyncBqInserter)
}
