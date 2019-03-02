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

	gaugeQueueSize = metric.NewInt(
		"qscheduler/state/queue_size",
		"The number of tasks in the queue.",
		nil,
		field.String("scheduler_id"),
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
	taskEvents  []*metrics.TaskEvent

	queueSize *int
}

// newMetricsBuffer creates a metrics sink for the given scheduler.
func newMetricsBuffer(schedulerID string) *metricsBuffer {
	return &metricsBuffer{schedulerID: schedulerID}
}

// reset resets the given metrics sink, erasing any previously added entries.
func (e *metricsBuffer) reset() {
	e.taskEvents = nil
	e.queueSize = nil
}

// flushToBQ flushes events to bigquery.
//
// This can be called inside of a datastore transaction, in which case events
// will only be flushed if the transaction succeeds.
func (e *metricsBuffer) flushToBQ(ctx context.Context) error {
	return eventlog.TaskEvents(ctx, e.taskEvents...)
}

// flushToTsMon flushes events to ts_mon.
func (e *metricsBuffer) flushToTsMon(ctx context.Context) error {
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
	if e.queueSize != nil {
		gaugeQueueSize.Set(ctx, int64(*e.queueSize), e.schedulerID)
	}
	return nil
}

// AddEvent implements scheduler.EventSink.
func (e *metricsBuffer) AddEvent(event *metrics.TaskEvent) {
	event.SchedulerId = e.schedulerID
	e.taskEvents = append(e.taskEvents, event)
}

// recordStateMetrics records general metrics about the given state.
func (e *metricsBuffer) recordStateMetrics(s *scheduler.Scheduler) {
	queueSize := len(s.GetWaitingRequests())
	e.queueSize = &queueSize
}

// recordProtoSize records a metric about a given proto's size.
func recordProtoSize(ctx context.Context, bytes int, schedulerID string, protoType string) {
	gaugeProtoSize.Set(ctx, int64(bytes), schedulerID, protoType)
}

// recordBatchSize records a metric about the number of requests handled within a batch.
func recordBatchSize(ctx context.Context, numRequests int, schedulerID string, success bool) {
	distributionOperationsPerBatch.Add(ctx, float64(numRequests), schedulerID, success)
}
