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

package mutaters

import (
	"testing"

	"infra/qscheduler/qslib/types"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

func stateForMutTest() *types.State {
	return &types.State{
		Balances: map[string]*vector.Vector{
			"a1": vector.New(),
			"a2": vector.New(1),
		},
		Requests: map[string]*task.Request{
			"t1": &task.Request{AccountId: "a2"},
		},
		Workers: map[string]*types.Worker{
			"w1": &types.Worker{
				RunningTask: &task.Run{
					Cost:      vector.New(.5, .5, .5),
					Priority:  1,
					Request:   &task.Request{AccountId: "a1"},
					RequestId: "t2",
				},
			},
			"w2": &types.Worker{},
		},
	}
}

func TestMutMatch(t *testing.T) {
	t.Parallel()
	state := stateForMutTest()
	mut := AssignIdleWorker{Priority: 1, RequestId: "t1", WorkerId: "w2"}
	mut.Mutate(state)
	w2 := state.Workers["w2"]
	if w2.RunningTask.Priority != 1 {
		t.Errorf("Got priority %d, want %d", w2.RunningTask.Priority, 1)
	}
	if w2.RunningTask.RequestId != "t1" {
		t.Errorf("Got task id %s, want %s", w2.RunningTask.RequestId, "t1")
	}
	_, ok := state.Requests["t1"]
	if ok {
		t.Errorf("task remains in queue")
	}
}

func TestMutReprioritize(t *testing.T) {
	t.Parallel()
	state := stateForMutTest()
	mut := ChangePriority{NewPriority: 2, WorkerId: "w1"}
	mut.Mutate(state)
	if state.Workers["w1"].RunningTask.Priority != 2 {
		t.Errorf("incorrect priority")
	}
}

func TestMutPreempt(t *testing.T) {
	t.Parallel()
	state := stateForMutTest()
	mut := PreemptTask{Priority: 0, RequestId: "t1", WorkerId: "w1"}
	mut.Mutate(state)

	gotId, wantId := state.Workers["w1"].RunningTask.RequestId, "t1"
	if gotId != wantId {
		t.Errorf("Got task id %s, want %s", gotId, wantId)
	}

	gotP, wantP := state.Workers["w1"].RunningTask.Priority, int32(0)
	if gotP != wantP {
		t.Errorf("Got priority %d, want %d", gotP, wantP)
	}

	gotC, wantC := state.Workers["w1"].RunningTask.Cost, *vector.New(.5, .5, .5)
	if !gotC.Equal(wantC) {
		t.Errorf("Got cost %+v, want %+v", gotC, wantC)
	}

	gotBal, wantBal := state.Balances["a2"], *vector.New(.5, -.5, -.5)
	if !gotBal.Equal(wantBal) {
		t.Errorf("Got paying account balance %+v, want %+v", gotBal, wantBal)
	}

	gotBal, wantBal = state.Balances["a1"], *vector.New(.5, .5, .5)
	if !gotBal.Equal(wantBal) {
		t.Errorf("Got receiving account balance %+v, want %+v", gotBal, wantBal)
	}
}
