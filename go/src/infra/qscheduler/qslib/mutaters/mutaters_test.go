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
			"t1": &task.Request{AccountId: "a2", Id: "t1"},
		},
		Workers: map[string]*types.Worker{
			"w1": &types.Worker{
				Id: "w1",
				RunningTask: &task.Run{
					Cost:     vector.New(.5, .5, .5),
					Priority: 1,
					Request:  &task.Request{Id: "t2", AccountId: "a1"},
				},
			},
			"w2": &types.Worker{Id: "w2"},
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
		t.Errorf("incorrect priority")
	}
	if w2.RunningTask.Request.Id != "t1" {
		t.Errorf("incorect task")
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
	if state.Workers["w1"].RunningTask.Request.Id != "t1" {
		t.Errorf("incorrect task on worker")
	}
	if state.Workers["w1"].RunningTask.Priority != 0 {
		t.Errorf("wrong priority")
	}
	if !state.Workers["w1"].RunningTask.Cost.Equal(*vector.New(.5, .5, .5)) {
		t.Errorf("task has wrong cost")
	}
	if !state.Balances["a2"].Equal(*vector.New(.5, -.5, -.5)) {
		t.Errorf("paying account balance incorrect %+v", state.Balances["a2"])
	}
	if !state.Balances["a1"].Equal(*vector.New(.5, .5, .5)) {
		t.Errorf("receiving account balance incorrect %+v", state.Balances["a1"])
	}
}
