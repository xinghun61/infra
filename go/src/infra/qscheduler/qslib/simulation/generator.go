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

package simulation

import (
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes/duration"
	"github.com/golang/protobuf/ptypes/timestamp"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/task"
)

// A GeneratedTask represents task that has been generated, along with
// metadata that is needed for simulating the task.
type GeneratedTask struct {
	// Request is the task that was generated.
	Request *task.Request
	// Duration is the amount of time that a simulation should allow a task to
	// run for before marking it as completed.
	Duration time.Duration
	// Id is the ID of the task that was generated.
	Id string
}

// advanceTo runs a generator forward to time t, and returns a slice
// of GeneratedTasks.
func (g *Generator) advanceTo(t time.Time, w *Workload) []GeneratedTask {
	gens := make([]GeneratedTask, 0)

	// Advance the generator in w.Period sized steps, such that its NextCycle
	// is at or after the current time t.
	for !t.Before(tutils.Timestamp(g.NextCycle)) {
		g.NextCycle = addTime(g.NextCycle, w.Period)

		// Generate new LabelSet if necessary.
		if g.LabelSetRemaining <= 0 {
			g.LabelSetId++
			g.LabelSetRemaining = w.CyclesPerLabelSet
		} else {
			g.LabelSetRemaining--
		}

		image := fmt.Sprintf("image_%s_%d", w.Tag, g.LabelSetId)

		// Generate and emit new jobs.
		for i := int32(0); i < w.Num; i++ {
			rid := fmt.Sprintf("req_%s_%d", w.Tag, g.ReqCount)
			gens = append(gens,
				GeneratedTask{
					Request: &task.Request{
						AccountId:   w.AccountId,
						EnqueueTime: tutils.TimestampProto(t),
						Labels:      []string{image},
					},
					Id:       rid,
					Duration: tutils.Duration(w.Duration),
				},
			)
			g.ReqCount++
		}
	}
	return gens
}

// NewGenerator creates a new Generator instance for supplied workload.
func NewGenerator(t0 time.Time, w *Workload) *Generator {
	return &Generator{
		NextCycle:         tutils.TimestampProto(t0.Add(tutils.Duration(w.Period))),
		LabelSetRemaining: w.CyclesPerLabelSet,
	}
}

// addTime adds duration d to time t, in protos.
func addTime(t *timestamp.Timestamp, d *duration.Duration) *timestamp.Timestamp {
	return tutils.TimestampProto(tutils.Timestamp(t).Add(tutils.Duration(d)))
}
