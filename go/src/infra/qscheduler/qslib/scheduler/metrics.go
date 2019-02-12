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

	"infra/qscheduler/qslib/metrics"
	"infra/qscheduler/qslib/tutils"
)

// MetricsSink defines the interface for a class that records scheduler
// metrics.
type MetricsSink interface {
	AddEvent(*metrics.TaskEvent)
}

// nullMetricsSink is a trivial implementation of MetricsSink that discards
// metrics.
type nullMetricsSink struct{}

// AddEvent implements MetricsSink.
func (m *nullMetricsSink) AddEvent(_ *metrics.TaskEvent) {}

// NullMetricsSink is a trivial MetricsSink that discards metrics.
var NullMetricsSink MetricsSink = &nullMetricsSink{}

// eventCommon returns a metrics.TaskEvent with fields populated that are common
// to all event types.
func eventCommon(request *TaskRequest, w *worker, s *state, t time.Time) *metrics.TaskEvent {
	var baseLabels sort.StringSlice = request.BaseLabels.ToSlice()
	var provLabels sort.StringSlice = request.ProvisionableLabels.ToSlice()
	var botID string
	var botLabels sort.StringSlice
	if w != nil {
		botID = string(w.ID)
		botLabels = w.labels.ToSlice()
		botLabels.Sort()
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
		ProvisionableLabels: provLabels,
		TaskId:              string(request.ID),
		Time:                tutils.TimestampProto(t),
	}
}

// eventEnqueued returns a TaskEvent for ENQUEUED events.
func eventEnqueued(request *TaskRequest, s *state, t time.Time) *metrics.TaskEvent {
	e := eventCommon(request, nil, s, t)
	e.EventType = metrics.TaskEvent_SWARMING_ENQUEUED
	return e
}

// eventAssigned returns a TaskEvent for ASSIGNED events.
func eventAssigned(request *TaskRequest, w *worker, s *state, t time.Time, details *metrics.TaskEvent_AssignedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_ASSIGNED
	e.Details = &metrics.TaskEvent_AssignedDetails_{AssignedDetails: details}
	return e
}

func eventPreempted(request *TaskRequest, w *worker, s *state, t time.Time, details *metrics.TaskEvent_PreemptedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_PREEMPTED
	e.Details = &metrics.TaskEvent_PreemptedDetails_{PreemptedDetails: details}
	return e
}

func eventReprioritized(request *TaskRequest, w *worker, s *state, t time.Time, details *metrics.TaskEvent_ReprioritizedDetails) *metrics.TaskEvent {
	e := eventCommon(request, w, s, t)
	e.EventType = metrics.TaskEvent_QSCHEDULER_REPRIORITIZED
	e.Details = &metrics.TaskEvent_ReprioritizedDetails_{ReprioritizedDetails: details}
	return e
}
