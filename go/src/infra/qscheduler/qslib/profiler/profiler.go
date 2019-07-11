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
	"fmt"
	"math/rand"
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

// StateParams defines size parameters used to construct a qscheduler state.
type StateParams struct {
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
func NewSchedulerState(params StateParams) *scheduler.Scheduler {
	ctx := context.Background()
	state := scheduler.New(time.Now())

	corpus := labelCorpus(params.LabelCorpusSize)

	addWorkers(ctx, time.Now(), params, corpus, state)

	addTasks(ctx, time.Now(), params, corpus, state)

	return state
}

func labelCorpus(size int) []string {
	labelCorpus := make([]string, size)
	for i := range labelCorpus {
		labelCorpus[i] = randomString()
	}
	return labelCorpus
}

func addWorkers(ctx context.Context, t time.Time, params StateParams, corpus []string, s *scheduler.Scheduler) {
	for i := 0; i < params.Workers; i++ {
		labels := stringset.New(params.LabelsPerWorker)
		for j := 0; j < params.LabelsPerWorker; j++ {
			labels.Add(corpus[rand.Intn(len(corpus))])
		}
		s.MarkIdle(ctx, scheduler.WorkerID(randomString()), labels, t, scheduler.NullEventSink)
	}
}

func addTasks(ctx context.Context, t time.Time, params StateParams, corpus []string, s *scheduler.Scheduler) {
	for i := 0; i < params.Tasks; i++ {
		labels := stringset.New(params.LabelsPerTask)
		for j := 0; j < params.LabelsPerTask; j++ {
			labels.Add(corpus[rand.Intn(len(corpus))])
		}
		provisionableLabel := corpus[rand.Intn(len(corpus))]
		request := scheduler.NewTaskRequest(
			scheduler.RequestID(randomString()),
			"foo-account-1",
			stringset.NewFromSlice(provisionableLabel),
			labels,
			t,
		)
		s.AddRequest(ctx, request, t, nil, scheduler.NullEventSink)
	}
}

// SimulationParams defines parameters for an iterated scheduler simulation.
type SimulationParams struct {
	// StateParams describes the per-iteration parameters of workers and requests
	// to create.
	StateParams StateParams

	Iterations int
}

// RunSimulation runs an iterated scheduler simulation.
func RunSimulation(params SimulationParams) {
	ctx := context.Background()
	t := time.Now()
	state := scheduler.New(t)
	// The preemption pass of scheduler has not yet been optimized for
	// large state size. Disable it for simulation purposes.
	state.Config().DisablePreemption = true
	state.Config().BotExpiration = tutils.DurationProto(time.Hour * 100)

	labels := labelCorpus(params.StateParams.LabelCorpusSize)

	for i := 0; i < params.Iterations; i++ {
		addTasks(ctx, t, params.StateParams, labels, state)
		addWorkers(ctx, t, params.StateParams, labels, state)
		state.UpdateTime(ctx, t)
		state.RunOnce(ctx, scheduler.NullEventSink)

		t = t.Add(1 * time.Minute)
		fmt.Printf("iter %d/%d\tworkers %d\tqueued tasks %d\trunning tasks %d\n", i+1, params.Iterations,
			len(state.GetWorkers()), len(state.GetWaitingRequests()), state.RunningRequests())
	}
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
