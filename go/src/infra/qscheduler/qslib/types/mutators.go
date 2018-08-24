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

package types

import (
	"fmt"

	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// Mutator is an interface that describes operations that mutate a State
// TODO: Consider moving this interface definition to scheduler package.
type Mutator interface {
	// Mutate modifies the given state, according to the behavior of the
	// Mutator.
	Mutate(state *State)
}

// Mutate implements Mutator.
//
// Assign a request to an idle worker. Panic if the worker wasn't previously idle.
func (m *AssignIdleWorker) Mutate(state *State) {
	w := state.Workers[m.WorkerId]
	if !w.IsIdle() {
		panic(fmt.Sprintf("Worker %s is not idle, it is running task %s.", m.WorkerId, w.RunningTask.RequestId))
	}
	rt := &task.Run{
		Priority:  m.Priority,
		Request:   state.Requests[m.RequestId],
		Cost:      vector.New(),
		RequestId: m.RequestId,
	}
	delete(state.Requests, m.RequestId)
	state.Workers[m.WorkerId].RunningTask = rt
}

// Mutate implements Mutator.
//
// Change the priority of a running task.
func (m *ChangePriority) Mutate(state *State) {
	state.Workers[m.WorkerId].RunningTask.Priority = m.NewPriority
}

// Mutate implements Mutator.
//
// Interrupt the current task on a worker with a new task. Reimburse the
// interrupted account with funds from the interrupting account.
func (m *PreemptTask) Mutate(state *State) {
	worker, ok := state.Workers[m.WorkerId]
	if !ok {
		panic(fmt.Sprintf("No worker with id %s", m.WorkerId))
	}

	cost := worker.RunningTask.Cost
	oldTask := worker.RunningTask

	newTask, ok := state.Requests[m.RequestId]
	if !ok {
		panic(fmt.Sprintf("No task with id %s", m.RequestId))
	}

	// Refund the cost of the preempted task, unless the old task's account no
	// longer exists.
	oldAcc := worker.RunningTask.Request.AccountId
	if _, ok := state.Balances[oldAcc]; ok {
		oldBal := state.Balances[oldAcc].Plus(*cost)
		state.Balances[oldAcc] = &oldBal
	}

	// Charge the preempting account for the cost of the preempted task.
	newAcc := newTask.AccountId
	newBal := state.Balances[newAcc].Minus(*cost)
	state.Balances[newAcc] = &newBal

	delete(state.Requests, m.RequestId)
	state.Requests[oldTask.RequestId] = oldTask.Request
	worker.RunningTask = &task.Run{Cost: cost, Priority: m.Priority, Request: newTask, RequestId: m.RequestId}
}
