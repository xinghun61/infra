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

	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"

	"infra/appengine/qscheduler-swarming/app/eventlog"
	"infra/qscheduler/qslib/protos/metrics"
)

var (
	counterCompleted = metric.NewCounter(
		"qscheduler/state/task_completed",
		"Task completed by swarming.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	counterEnqueued = metric.NewCounter(
		"qscheduler/state/task_enqueued",
		"Task enqueued by swarming.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	counterAssigned = metric.NewCounter(
		"qscheduler/state/task_assigned",
		"Task assigned by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
		field.Bool("preempting"),
		field.Bool("provision_required"),
	)

	counterPreempted = metric.NewCounter(
		"qscheduler/state/task_preempted",
		"Task preempted by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	counterReprioritized = metric.NewCounter(
		"qscheduler/state/task_reprioritized",
		"Task reprioritized by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)
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
	for _, event := range e.taskEvents {
		switch event.EventType {
		case metrics.TaskEvent_SWARMING_COMPLETED:
			counterCompleted.Add(ctx, 1, event.SchedulerId, event.AccountId)
		case metrics.TaskEvent_SWARMING_ENQUEUED:
			counterEnqueued.Add(ctx, 1, event.SchedulerId, event.AccountId)
		case metrics.TaskEvent_QSCHEDULER_ASSIGNED:
			details := event.GetAssignedDetails()
			counterAssigned.Add(ctx, 1, event.SchedulerId, event.AccountId, details.Preempting, details.ProvisionRequired)
		case metrics.TaskEvent_QSCHEDULER_PREEMPTED:
			counterPreempted.Add(ctx, 1, event.SchedulerId, event.AccountId)
		case metrics.TaskEvent_QSCHEDULER_REPRIORITIZED:
			counterReprioritized.Add(ctx, 1, event.SchedulerId, event.AccountId)
		}
	}
	return nil
}

// AddEvent implements scheduler.EventSink.
func (e *eventBuffer) AddEvent(event *metrics.TaskEvent) {
	event.SchedulerId = e.schedulerID
	e.taskEvents = append(e.taskEvents, event)
}
