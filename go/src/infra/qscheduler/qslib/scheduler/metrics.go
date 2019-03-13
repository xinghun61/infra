// Copyright 2018 The LUCI Authors.
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

package scheduler

import (
	"sort"
	"time"

	"infra/qscheduler/qslib/protos/metrics"
	"infra/qscheduler/qslib/tutils"
)

// EventSink defines the interface for a class that records scheduler
// events, for metrics or analytics purposes.
type EventSink interface {
	AddEvent(*metrics.TaskEvent)
}

// nullEventSink is a trivial implementation of MetricsSink that discards
// metrics.
type nullEventSink struct{}

// AddEvent implements EventSink.
func (m *nullEventSink) AddEvent(_ *metrics.TaskEvent) {}

// NullEventSink is a trivial MetricsSink that discards metrics.
var NullEventSink EventSink = &nullEventSink{}

// eventCommon returns a metrics.TaskEvent with fields populated that are common
// to all event types.
func eventCommon(request *TaskRequest, w *Worker, s *state, t time.Time) *metrics.TaskEvent {
	var baseLabels sort.StringSlice = request.BaseLabels.ToSlice()
	var provLabels sort.StringSlice = request.ProvisionableLabels.ToSlice()
	var botID string
	var botLabels sort.StringSlice
	var cost []float32
	if w != nil {
		botID = string(w.ID)
		botLabels = w.Labels.ToSlice()
		botLabels.Sort()
		cost = w.runningTask.cost[:]
	}
	baseLabels.Sort()
	provLabels.Sort()
	accountBalance, accountValid := s.balances[request.AccountID]
	return &metrics.TaskEvent{
		AccountBalance:      accountBalance[:],
		AccountId:           string(request.AccountID),
		AccountValid:        accountValid,
		BaseLabels:          baseLabels,
		BotId:               botID,
		BotDimensions:       botLabels,
		Cost:                cost,
		ProvisionableLabels: provLabels,
		TaskId:              string(request.ID),
		Time:                tutils.TimestampProto(t),
	}
}

// eventEnqueued returns a TaskEvent for ENQUEUED events.
func eventEnqueued(request *TaskRequest, s *state, t time.Time, details *metrics.TaskEvent_EnqueuedDetails) *metrics.TaskEvent {
	e := eventCommon(request, nil, s, t)
	e.EventType = metrics.TaskEvent_SWARMING_ENQUEUED
	e.Category = metrics.TaskEvent_CATEGORY_SWARMING
	e.Details = &metrics.TaskEvent_EnqueuedDetails_{EnqueuedDetails: details}
	return e
}

// eventAssigned returns a TaskEvent for ASSIGNED events.
func eventAssigned(request *TaskRequest, w *Worker, s *state, t time.Time, details *metrics.TaskEvent_AssignedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_ASSIGNED
	e.Category = metrics.TaskEvent_CATEGORY_QSCHEDULER
	e.Details = &metrics.TaskEvent_AssignedDetails_{AssignedDetails: details}
	return e
}

// eventPreempted returns a TaskEvent for PREEMPTED events.
func eventPreempted(request *TaskRequest, w *Worker, s *state, t time.Time, details *metrics.TaskEvent_PreemptedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_PREEMPTED
	e.Category = metrics.TaskEvent_CATEGORY_QSCHEDULER
	e.Details = &metrics.TaskEvent_PreemptedDetails_{PreemptedDetails: details}
	return e
}

// eventReprioritized returns a TaskEvent for REPRIORITIZED events.
func eventReprioritized(request *TaskRequest, w *Worker, s *state, t time.Time, details *metrics.TaskEvent_ReprioritizedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_REPRIORITIZED
	e.Category = metrics.TaskEvent_CATEGORY_QSCHEDULER
	e.Details = &metrics.TaskEvent_ReprioritizedDetails_{ReprioritizedDetails: details}
	return e
}

// eventCompleted returns a TaskEvent for COMPLETED events.
func eventCompleted(request *TaskRequest, w *Worker, s *state, t time.Time, details *metrics.TaskEvent_CompletedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_SWARMING_COMPLETED
	e.Category = metrics.TaskEvent_CATEGORY_SWARMING
	e.Details = &metrics.TaskEvent_CompletedDetails_{CompletedDetails: details}
	return e
}
