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
	"fmt"
	"testing"

	"github.com/kylelemons/godebug/pretty"

	"infra/qscheduler/qslib/types/vector"
)

// TestApplyIdleAssignment tests that Apply for IDLE_WORKER behaves correctly.
func TestApplyIdleAssignment(t *testing.T) {
	t.Parallel()
	state := &State{
		QueuedRequests: map[string]*TaskRequest{"t1": &TaskRequest{}},
		Workers:        map[string]*Worker{"w1": NewWorker()},
	}

	expect := &State{
		QueuedRequests: map[string]*TaskRequest{},
		Workers: map[string]*Worker{
			"w1": &Worker{RunningTask: &TaskRun{
				RequestId: "t1",
				Priority:  1,
				Request:   &TaskRequest{},
				Cost:      vector.New()}},
		},
		RunningRequestsCache: map[string]string{"t1": "w1"},
	}

	mut := &Assignment{Type: Assignment_IDLE_WORKER, Priority: 1, RequestId: "t1", WorkerId: "w1"}
	state.applyAssignment(mut)

	if diff := pretty.Compare(state, expect); diff != "" {
		t.Errorf(fmt.Sprintf("Unexpected state diff (-got +want): %s", diff))
	}
}

// TestApplyPreempt tests that Apply for PREEMPT_WORKER behaves correctly.
func TestApplyPreempt(t *testing.T) {
	t.Parallel()
	state := &State{
		Balances: map[string]*vector.Vector{
			"a1": vector.New(),
			"a2": vector.New(2),
		},
		QueuedRequests: map[string]*TaskRequest{
			"t2": &TaskRequest{AccountId: "a2"},
		},
		Workers: map[string]*Worker{
			"w1": &Worker{RunningTask: &TaskRun{
				Cost:      vector.New(1),
				Priority:  2,
				Request:   &TaskRequest{AccountId: "a1"},
				RequestId: "t1",
			}},
		},
	}

	expect := &State{
		Balances: map[string]*vector.Vector{
			"a1": vector.New(1),
			"a2": vector.New(1),
		},
		QueuedRequests: map[string]*TaskRequest{
			"t1": &TaskRequest{AccountId: "a1"},
		},
		Workers: map[string]*Worker{
			"w1": &Worker{RunningTask: &TaskRun{
				Cost:      vector.New(1),
				Priority:  1,
				Request:   &TaskRequest{AccountId: "a2"},
				RequestId: "t2",
			},
			}},
		RunningRequestsCache: map[string]string{"t2": "w1"},
	}

	mut := &Assignment{Type: Assignment_PREEMPT_WORKER, Priority: 1, RequestId: "t2", WorkerId: "w1", TaskToAbort: "t1"}
	state.applyAssignment(mut)

	if diff := pretty.Compare(state, expect); diff != "" {
		t.Errorf(fmt.Sprintf("Unexpected state diff (-got +want): %s", diff))
	}
}
