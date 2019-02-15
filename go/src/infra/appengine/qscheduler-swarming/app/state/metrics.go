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

package state

import (
	"context"

	"infra/appengine/qscheduler-swarming/app/eventlog"
	"infra/qscheduler/qslib/protos/metrics"
)

// eventBuffer implements scheduler.EventSink.
//
// Events can be flushed to bigquery.
type eventBuffer struct {
	schedulerID string
	taskEvents  []*metrics.TaskEvent
}

// newEventBuffer creates a metrics sink for the given scheduler.
func newEventBuffer(schedulerID string) *eventBuffer {
	return &eventBuffer{schedulerID: schedulerID}
}

// reset resets the given metrics sink, erasing any previously added entries.
func (e *eventBuffer) reset() {
	e.taskEvents = nil
}

// flushToBQ flushes events to bigquery.
//
// This can be called inside of a datastore transaction, in which case events
// will only be flushed if the transaction succeeds.
func (e *eventBuffer) flushToBQ(ctx context.Context) error {
	return eventlog.TaskEvents(ctx, e.taskEvents...)
}

// flushToTsMon flushes events to ts_mon.
func (e *eventBuffer) flushToTsMon(ctx context.Context) error {
	// TODO(akeshet): Implement.
	return nil
}

// AddEvent implements scheduler.EventSink.
func (e *eventBuffer) AddEvent(event *metrics.TaskEvent) {
	event.SchedulerId = e.schedulerID
	e.taskEvents = append(e.taskEvents, event)
}
