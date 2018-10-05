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

package reconciler

import (
	"fmt"
	"testing"
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"

	"github.com/kylelemons/godebug/pretty"
)

// TestQuotaschedulerInterface ensures that scheduler.Scheduler is a valid
// implementation of the Scheduler interface.
func TestQuotaschedulerInterface(t *testing.T) {
	var s interface{} = &scheduler.Scheduler{}
	if _, ok := s.(Scheduler); !ok {
		t.Errorf("Scheduler interface should be implemented by *scheduler.Scheduler")
	}
}

func assertAssignments(t *testing.T, description string,
	got []Assignment, want []Assignment) {
	t.Helper()
	if diff := pretty.Compare(got, want); diff != "" {
		t.Errorf(fmt.Sprintf("%s got unexpected assignment diff (-got +want): %s", description, diff))
	}
}

// TestOneAssignment tests that a scheduler assignment for a single idle
// worker is correctly assigned, and that subsequent calls prior to
// ack return the same assignment.
func TestOneAssignment(t *testing.T) {
	fs := newFakeScheduler()
	state := New()

	epoch := time.Unix(0, 0)
	ti := epoch
	fs.fakeSchedule(&scheduler.Assignment{
		RequestId: "r1",
		WorkerId:  "w1",
		Type:      scheduler.Assignment_IDLE_WORKER,
		Time:      tutils.TimestampProto(ti),
	})

	idleWorkers := []*IdleWorker{
		&IdleWorker{"w1", []string{}},
	}

	// Assign once for worker "w1".
	got := state.AssignTasks(fs, idleWorkers, ti)
	want := []Assignment{Assignment{"w1", "r1"}}
	assertAssignments(t, "Simple single-worker assignment call", got, want)

	// Subsequent AssignTasks should return the same assignment, as it has not been
	// ack'd.
	ti = ti.Add(1)
	got = state.AssignTasks(fs, idleWorkers, ti)
	assertAssignments(t, "Second assignment call", got, want)
}

// TestQueuedAssignment tests that a scheduler assignment is queued until
// the relevant worker becomes idle, even if that worker was previously given
// its assignment by the scheduler.
func TestQueuedAssignment(t *testing.T) {
	fakeSch := newFakeScheduler()
	state := New()

	epoch := time.Unix(0, 0)
	ti := epoch

	w1 := []*IdleWorker{
		&IdleWorker{"w1", []string{}},
	}
	w2 := []*IdleWorker{
		&IdleWorker{"w2", []string{}},
	}

	// Mark w1 as idle, prior to any assignment for it.
	got := state.AssignTasks(fakeSch, w1, ti)
	assertAssignments(t, "Pre-assignment call", got, []Assignment{})

	// Give an assignment to w1, but make call for w2.
	ti = ti.Add(1)
	fakeSch.fakeSchedule(&scheduler.Assignment{
		RequestId: "r1",
		WorkerId:  "w1",
		Type:      scheduler.Assignment_IDLE_WORKER,
		Time:      tutils.TimestampProto(ti),
	})
	got = state.AssignTasks(fakeSch, w2, ti)
	assertAssignments(t, "Post-assignment call for w2", got, []Assignment{})

	// Assign for w1.
	ti = ti.Add(1)
	got = state.AssignTasks(fakeSch, w1, ti)
	want := []Assignment{Assignment{"w1", "r1"}}
	assertAssignments(t, "Post-assignment call for w1", got, want)
}

// TestNotifyNewTask ensures that Notify for a NEW task results in that task
// being enqueued, and later scheduled.
func TestNotifyNewTask(t *testing.T) {
	r := New()
	s := &fifoScheduler{}

	r.Notify(s, &TaskUpdate{
		Type:      TaskUpdate_NEW,
		RequestId: "r1",
	})

	epoch := time.Unix(0, 0)
	got := r.AssignTasks(s, []*IdleWorker{&IdleWorker{ID: "w1"}}, epoch)
	want := []Assignment{Assignment{"w1", "r1"}}
	assertAssignments(t, "New task", got, want)
}
