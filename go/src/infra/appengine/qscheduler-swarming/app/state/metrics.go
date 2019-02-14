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
	"infra/qscheduler/qslib/protos/metrics"
)

// metricsSliceSink implements scheduler.MetricsSink by appending items to
// a slice.
type metricsSliceSink struct {
	schedulerID string
	taskEvents  []*metrics.TaskEvent
}

// newMetricsSink creates a metrics sink for the given scheduler.
func newMetricsSink(schedulerID string) *metricsSliceSink {
	return &metricsSliceSink{schedulerID: schedulerID}
}

// AddEvent implements scheduler.MetricsSink.
func (m *metricsSliceSink) AddEvent(e *metrics.TaskEvent) {
	e.SchedulerId = m.schedulerID
	m.taskEvents = append(m.taskEvents, e)
}
