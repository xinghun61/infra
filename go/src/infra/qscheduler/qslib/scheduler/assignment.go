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

	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"
)

// apply applies an Assignment, putting the appropriate task request
// on a worker and re-enqueueing and refunding old tasks if necessary.
func (m *Assignment) apply(state *State) {
	worker, ok := state.Workers[m.WorkerId]
	if !ok {
		panic(fmt.Sprintf("No worker with id %s", m.WorkerId))
	}

	cost := vector.New()
	newTask := state.Requests[m.RequestId]

	// If we are a preempt mutator and there is a task running, then re-enqueue it
	// and apply refund.
	if !worker.isIdle() {
		if m.Type == Assignment_IDLE_WORKER {
			panic(fmt.Sprintf("Worker %s is not idle, it is running task %s.",
				m.WorkerId, worker.RunningTask.RequestId))
		}
		if m.Type == Assignment_PREEMPT_WORKER {
			oldTask := worker.RunningTask
			cost = oldTask.Cost

			// Refund the cost of the preempted task, unless the old task's account no
			// longer exists.
			oldAcc := oldTask.Request.AccountId
			if _, ok := state.Balances[oldAcc]; ok {
				oldBal := state.Balances[oldAcc].Plus(*cost)
				state.Balances[oldAcc] = &oldBal
			}

			// Charge the preempting account for the cost of the preempted task.
			newAcc := newTask.AccountId
			newBal := state.Balances[newAcc].Minus(*cost)
			state.Balances[newAcc] = &newBal

			// Reenqueue the old task.
			state.Requests[oldTask.RequestId] = oldTask.Request
		}

	}

	rt := &task.Run{
		Priority:  m.Priority,
		Request:   state.Requests[m.RequestId],
		Cost:      cost,
		RequestId: m.RequestId,
	}
	delete(state.Requests, m.RequestId)
	state.Workers[m.WorkerId].RunningTask = rt
}
