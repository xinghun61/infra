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

	"go.chromium.org/luci/common/tsmon/distribution"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"

	"infra/appengine/qscheduler-swarming/app/eventlog"
	"infra/qscheduler/qslib/protos/metrics"
	"infra/qscheduler/qslib/scheduler"
)

var (
	counterCompleted = metric.NewCounter(
		"qscheduler/state/event/task_completed",
		"Task completed by swarming.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
		field.String("reason"),
	)

	counterEnqueued = metric.NewCounter(
		"qscheduler/state/event/task_enqueued",
		"Task enqueued by swarming.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	counterAssigned = metric.NewCounter(
		"qscheduler/state/event/task_assigned",
		"Task assigned by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
		field.Bool("preempting"),
		field.Bool("provision_required"),
	)

	counterPreempted = metric.NewCounter(
		"qscheduler/state/event/task_preempted",
		"Task preempted by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	counterReprioritized = metric.NewCounter(
		"qscheduler/state/event/task_reprioritized",
		"Task reprioritized by qscheduler.",
		nil,
		field.String("scheduler_id"),
		field.String("account_id"),
	)

	// TODO(akeshet): Deprecate and delete this metric in favor of
	// qscheduler/state/task_state which already incorporates it.
	gaugeQueueSize = metric.NewInt(
		"qscheduler/state/queue_size",
		"The number of tasks in the queue.",
		nil,
		field.String("scheduler_id"),
	)

	gaugeTaskState = metric.NewInt(
		"qscheduler/state/task",
		"The number of tasks in a given state.",
		nil,
		field.String("scheduler_id"),
		field.String("state"),
		field.Int("priority"),
	)

	gaugeBotState = metric.NewInt(
		"qscheduler/state/bot",
		"The number of bots in a given state.",
		nil,
		field.String("scheduler_id"),
		field.String("state"),
		field.Int("priority"),
	)

	gaugeProtoSize = metric.NewInt(
		"qscheduler/store/proto_size",
		"Size of a loaded store proto.",
		&types.MetricMetadata{
			Units: types.Bytes,
		},
		field.String("scheduler_id"),
		field.String("type"),
	)

	distributionOperationsPerBatch = metric.NewCumulativeDistribution(
		"qscheduler/state/batcher/operations",
		"Number of operations handled within a batch.",
		nil,
		distribution.FixedWidthBucketer(1, 100),
		field.String("scheduler_id"),
		field.Bool("success"),
	)
)

// metricsBuffer implements scheduler.EventSink.
//
// Metrics are buffered so that they can be sent to bigquery and tsmon upon
// successful datastore transaction.
type metricsBuffer struct {
	schedulerID string
	taskEvents  *[]*metrics.TaskEvent
	isCallback  *bool
}

// newMetricsBuffer creates a metrics sink for the given scheduler.
func newMetricsBuffer(schedulerID string) *metricsBuffer {
	return &metricsBuffer{
		schedulerID: schedulerID,
		taskEvents:  &[]*metrics.TaskEvent{},
	}
}

// reset resets the given metrics sink, erasing any previously added entries.
func (e *metricsBuffer) reset() {
	e.taskEvents = &[]*metrics.TaskEvent{}
}

// flushToBQ flushes events to bigquery.
//
// This can be called inside of a datastore transaction, in which case events
// will only be flushed if the transaction succeeds.
func (e *metricsBuffer) flushToBQ(ctx context.Context) error {
	return eventlog.TaskEvents(ctx, *e.taskEvents...)
}

// flushToTsMon flushes events to ts_mon.
func (e *metricsBuffer) flushToTsMon(ctx context.Context) error {
	for _, event := range *e.taskEvents {
		switch event.EventType {
		case metrics.TaskEvent_SWARMING_COMPLETED:
			details := event.GetCompletedDetails()
			counterCompleted.Add(ctx, 1, event.SchedulerId, event.AccountId, details.Reason.String())
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
func (e *metricsBuffer) AddEvent(event *metrics.TaskEvent) {
	event.SchedulerId = e.schedulerID
	if e.isCallback != nil {
		event.IsCallback = *e.isCallback
	}
	*e.taskEvents = append(*e.taskEvents, event)
}

// WithFields implements scheduler.EventSink.
func (e *metricsBuffer) WithFields(isCallback bool) scheduler.EventSink {
	return &metricsBuffer{
		isCallback:  &isCallback,
		schedulerID: e.schedulerID,
		taskEvents:  e.taskEvents,
	}
}

// recordStateGaugeMetrics records general gauge metrics about the given state.
//
// As new metrics are added, gauge metrics about a state should be emitted here.
// Because none of the metrics emitted herein are cumulative, it doesn't matter
// if this is called within a datastore transaction or not, or whether the
// transaction that called it succeeds.
func recordStateGaugeMetrics(ctx context.Context, s *scheduler.Scheduler, schedulerID string) {
	gaugeQueueSize.Set(ctx, int64(len(s.GetWaitingRequests())), schedulerID)

	var runningPerPriority [scheduler.NumPriorities + 1]int64
	var idleBots int64
	for _, w := range s.GetWorkers() {
		if w.IsIdle() {
			idleBots++
		} else {
			priority := int(w.RunningPriority())
			if priority < 0 {
				priority = 0
			}
			if priority > scheduler.NumPriorities {
				priority = scheduler.NumPriorities
			}
			runningPerPriority[priority]++
		}
	}
	// TODO(akeshet): Include accurate information on priority of queued tasks, rather than arbitrary NumPriorities value.
	gaugeTaskState.Set(ctx, int64(len(s.GetWaitingRequests())), schedulerID, "waiting", scheduler.NumPriorities)
	gaugeBotState.Set(ctx, idleBots, schedulerID, "idle", scheduler.NumPriorities)
	for priority, val := range runningPerPriority {
		gaugeTaskState.Set(ctx, val, schedulerID, "running", priority)
		gaugeBotState.Set(ctx, val, schedulerID, "running", priority)
	}
}

// recordProtoSize records a metric about a given proto's size.
func recordProtoSize(ctx context.Context, bytes int, schedulerID string, protoType string) {
	gaugeProtoSize.Set(ctx, int64(bytes), schedulerID, protoType)
}

// recordBatchSize records a metric about the number of requests handled within a batch.
func recordBatchSize(ctx context.Context, numRequests int, schedulerID string, success bool) {
	distributionOperationsPerBatch.Add(ctx, float64(numRequests), schedulerID, success)
}
