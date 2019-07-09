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

// Package profiler provides entity size and CPU usage profiling for quotascheduler
// entities.
package profiler

import (
	"context"
	"math/rand"
	"time"

	"infra/qscheduler/qslib/scheduler"

	"go.chromium.org/luci/common/data/stringset"
)

// Params defines size parameters used to construct a qscheduler state.
type Params struct {
	// LabelCorpusSize is the number of unique labels referenced by tasks
	// or workers.
	LabelCorpusSize int

	LabelsPerTask   int
	LabelsPerWorker int
	Workers         int
	Tasks           int
}

// NewSchedulerState returns a proto-representation of a qscheduler state, with
// given size parameters.
func NewSchedulerState(params Params) *scheduler.Scheduler {
	ctx := context.Background()
	state := scheduler.New(time.Now())

	labelCorpus := make([]string, params.LabelCorpusSize)
	for i := range labelCorpus {
		labelCorpus[i] = randomString()
	}

	for i := 0; i < params.Workers; i++ {
		labels := stringset.New(params.LabelsPerWorker)
		for j := 0; j < params.LabelsPerWorker; j++ {
			labels.Add(labelCorpus[rand.Intn(len(labelCorpus))])
		}
		state.MarkIdle(ctx, scheduler.WorkerID(randomString()), labels, time.Now(), scheduler.NullEventSink)
	}

	for i := 0; i < params.Tasks; i++ {
		labels := stringset.New(params.LabelsPerTask)
		for j := 0; j < params.LabelsPerTask; j++ {
			labels.Add(labelCorpus[rand.Intn(len(labelCorpus))])
		}
		request := scheduler.NewTaskRequest(
			scheduler.RequestID(randomString()),
			"foo-account-1",
			nil,
			labels,
			time.Now(),
		)
		state.AddRequest(ctx, request, time.Now(), nil, scheduler.NullEventSink)
	}

	return state
}

var letters = []byte("abcdefghijklmnopqsrtuvwxyz")

// randomString returns a string of similar entropy and size as
// a swarming task id, a bot id, or a label.
func randomString() string {
	bytes := make([]byte, 16)
	for i := range bytes {
		bytes[i] = letters[rand.Intn(len(letters))]
	}
	return string(bytes)
}
