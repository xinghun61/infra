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
	"context"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/luci/common/data/stringset"
)

// TestMarkIdle tests that a new worker is marked idle by MarkIdle, and that
// a subsequent updates to it are only respected if their timestamp is newer
// that the previous one.
func TestMarkIdle(t *testing.T) {
	tm0 := time.Unix(0, 0)
	tm1 := time.Unix(1, 0)
	tm2 := time.Unix(2, 0)
	Convey("Given an empty state", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		workerID := WorkerID("w1")
		Convey("when a worker marked idle at t=1", func() {
			label1 := stringset.NewFromSlice("old_label")
			state.markIdle(workerID, label1, tm1)
			Convey("then the worker is added to the state.", func() {
				So(state.workers, ShouldContainKey, workerID)
				So(state.workers[workerID].labels, ShouldResemble, label1)
			})
			Convey("when marking idle again with newer time t=2", func() {
				state.markIdle(workerID, stringset.NewFromSlice("new_label"), tm2)
				Convey("then the update is applied.", func() {
					So(state.workers[workerID].labels, ShouldResemble, stringset.NewFromSlice("new_label"))
				})
			})
			Convey("when marking idle again with older time t=0", func() {
				state.markIdle(workerID, stringset.NewFromSlice("new_label"), tm0)
				Convey("then the update is ignored.", func() {
					So(state.workers[workerID].labels, ShouldResemble, label1)
				})
			})
		})

		Convey("given a worker running a task at t=1", func() {
			state.markIdle(workerID, stringset.New(0), tm1)
			state.addRequest(ctx, NewTaskRequest("r1", "", nil, nil, tm1), tm1, NullMetricsSink)
			state.applyAssignment(&Assignment{Type: AssignmentIdleWorker, RequestID: "r1", WorkerID: workerID})
			Convey("when marking idle again with newer time t=2", func() {
				state.markIdle(workerID, stringset.New(0), tm2)
				Convey("then the update is applied.", func() {
					So(state.workers[workerID].isIdle(), ShouldBeTrue)
					So(state.workers[workerID].confirmedTime, ShouldEqual, tm2)
				})
			})

			Convey("when marking idle again with older time t=0", func() {
				state.markIdle(workerID, stringset.New(0), tm0)
				Convey("then the update is ignored.", func() {
					So(state.workers[workerID].isIdle(), ShouldBeFalse)
					So(state.workers[workerID].confirmedTime, ShouldEqual, tm1)
				})
			})
		})
	})
}

func TestnotifyRequest(ctx, t *testing.T) {
	tm0 := time.Unix(0, 0)
	tm1 := time.Unix(1, 0)
	tm2 := time.Unix(2, 0)
	tm3 := time.Unix(3, 0)
	tm4 := time.Unix(4, 0)
	Convey("Given a state with a request(t=1) and idle worker(t=3) and a match between them", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		state.addRequest(ctx, NewTaskRequest("r1", "", nil, nil, tm1), tm1, NullMetricsSink)
		state.markIdle("w1", stringset.New(0), tm3)
		a := &Assignment{
			Type:      AssignmentIdleWorker,
			WorkerID:  "w1",
			RequestID: "r1",
		}
		state.applyAssignment(a)
		Convey("when notifying (idle request) with an older time t=0", func() {
			state.notifyRequest(ctx, "r1", "", tm0)
			Convey("then the update is ignored.", func() {
				So(state.queuedRequests, ShouldHaveLength, 0)
				So(state.workers, ShouldContainKey, "w1")
				So(state.workers["w1"].runningTask, ShouldNotBeNil)
				So(state.workers["w1"].runningTask.request.ID, ShouldEqual, "r1")
			})
		})
		Convey("when notifying (idle request) with an intermediate time (between current request and worker time) t=1", func() {
			state.notifyRequest(ctx, "r1", "", tm2)
			Convey("then the update is ignored.", func() {
				So(state.queuedRequests, ShouldHaveLength, 0)
				So(state.workers, ShouldContainKey, "w1")
				So(state.workers["w1"].runningTask, ShouldNotBeNil)
				So(state.workers["w1"].runningTask.request.ID, ShouldEqual, "r1")
			})
		})
		Convey("when notifying (idle request) with newer time t=4", func() {
			state.notifyRequest(ctx, "r1", "", tm4)
			Convey("then the worker is deleted.", func() {
				So(state.workers, ShouldNotContainKey, "w1")
			})
			Convey("then the request is deleted.", func() {
				So(state.queuedRequests, ShouldContainKey, "r1")
			})
			Convey("then the request time is updated.", func() {
				So(state.queuedRequests["r1"].confirmedTime, ShouldEqual, tm4)
			})
		})
		Convey("when notifying (idle request) with the same time as the worker", func() {
			state.notifyRequest(ctx, "r1", "", tm3)
			Convey("then the worker is deleted.", func() {
				So(state.workers, ShouldNotContainKey, "w1")
			})
			Convey("then the request is deleted.", func() {
				So(state.queuedRequests, ShouldContainKey, "r1")
			})
			Convey("then the request time is updated.", func() {
				So(state.queuedRequests["r1"].confirmedTime, ShouldEqual, tm3)
			})
		})

		Convey("when notifying (correct match) with older time t=0", func() {
			state.notifyRequest(ctx, "r1", "w1", tm0)
			Convey("then the update is ignored.", func() {
				So(state.queuedRequests, ShouldHaveLength, 0)
				So(state.workers, ShouldContainKey, "w1")
				So(state.workers["w1"].runningTask, ShouldNotBeNil)
				So(state.workers["w1"].runningTask.request.ID, ShouldEqual, "r1")
			})
		})
		Convey("when notifying (correct match) with intermediate time t=2", func() {
			state.notifyRequest(ctx, "r1", "w1", tm2)
			Convey("then the request time is updated.", func() {
				So(state.workers["w1"].runningTask.request.confirmedTime, ShouldEqual, tm2)
			})
		})
		Convey("when notifying (correct match) with newer time t=4", func() {
			state.notifyRequest(ctx, "r1", "w1", tm4)
			Convey("then the request time is updated.", func() {
				So(state.workers["w1"].runningTask.request.confirmedTime, ShouldEqual, tm4)
			})
			Convey("then the worker time is updated.", func() {
				So(state.workers["w1"].confirmedTime, ShouldEqual, tm4)
			})
		})
	})

	Convey("Given a state with a matched request and worker both at t=1 and a separate idle worker at t=3", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		state.addRequest(ctx, NewTaskRequest("r1", "", nil, nil, tm1), tm1, NullMetricsSink)
		state.markIdle("w1", stringset.New(0), tm1)
		state.markIdle("w2", stringset.New(0), tm3)
		a := &Assignment{
			Type:      AssignmentIdleWorker,
			WorkerID:  "w1",
			RequestID: "r1",
		}
		state.applyAssignment(a)
		Convey("when notifying (contradictory match) with an older time t=0", func() {
			state.notifyRequest(ctx, "r1", "w2", tm0)
			Convey("then the update is ignored.", func() {
				So(state.workers, ShouldContainKey, "w1")
				So(state.workers["w1"].runningTask, ShouldNotBeNil)
				So(state.workers["w1"].runningTask.request.ID, ShouldEqual, "r1")
				So(state.workers, ShouldContainKey, "w2")
				So(state.workers["w2"].runningTask, ShouldBeNil)
			})
		})
		Convey("when notifying (contradictory match) with a time newer than match but older than idle worker t=2", func() {
			state.notifyRequest(ctx, "r1", "w2", tm2)
			Convey("then the matching worker and request are deleted.", func() {
				So(state.queuedRequests, ShouldNotContainKey, "r1")
				So(state.workers, ShouldNotContainKey, "w1")
			})
		})

		Convey("when notifying (contradictory match) with a newer time t=4", func() {
			state.notifyRequest(ctx, "r1", "w2", tm4)
			Convey("then the request and both workers are deleted.", func() {
				So(state.workers, ShouldBeEmpty)
				So(state.queuedRequests, ShouldBeEmpty)
			})
		})

	})

	Convey("Given a state with an idle worker(t=1), and a notify call with a match to an unknown request for that worker", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		state.markIdle("w1", stringset.New(0), tm1)
		Convey("when notifying (unknown request for worker) with older time t=0", func() {
			state.notifyRequest(ctx, "r1", "w1", tm0)
			Convey("then the update is ignored.", func() {
				So(state.queuedRequests, ShouldBeEmpty)
				So(state.workers, ShouldContainKey, "w1")
				So(state.workers["w1"].runningTask, ShouldBeNil)
			})
		})
		Convey("when notifying (unknown request for worker) with equal time t=1", func() {
			state.notifyRequest(ctx, "r1", "w1", tm1)
			Convey("then the worker is deleted.", func() {
				So(state.workers, ShouldNotContainKey, "w1")
			})
		})
		Convey("when notifying (unknown request for worker) with newer time t=2", func() {
			state.notifyRequest(ctx, "r1", "w1", tm2)
			Convey("then the worker is deleted.", func() {
				So(state.workers, ShouldNotContainKey, "w1")
			})
		})
	})
}

func TestabortRequest(ctx, t *testing.T) {
	tm0 := time.Unix(0, 0)
	tm1 := time.Unix(1, 0)
	tm2 := time.Unix(2, 0)
	reqID := RequestID("request1")
	wID := WorkerID("worker1")
	Convey("Given a state with one request and one idle worker", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		state.addRequest(ctx, NewTaskRequest(reqID, "", nil, nil, tm1), tm1, NullMetricsSink)
		state.markIdle(wID, stringset.New(0), tm1)
		Convey("when AbortRequest with forward time is called for that request", func() {
			state.abortRequest(ctx, reqID, tm2)
			Convey("then the request is deleted, the worker is unmodified.", func() {
				So(state.queuedRequests, ShouldNotContainKey, reqID)
				So(state.workers, ShouldHaveLength, 1)
			})
		})
		Convey("when AbortRequest with backward time is called for that request", func() {
			state.abortRequest(ctx, reqID, tm0)
			Convey("then request and worker should remain.", func() {
				So(state.queuedRequests, ShouldContainKey, reqID)
				So(state.workers, ShouldHaveLength, 1)
			})
		})
	})

	Convey("Given a state with a request running on a worker", t, func() {
		ctx := context.Background()
		state := newState(tm0)
		state.addRequest(ctx, NewTaskRequest(reqID, "", nil, nil, tm1), tm1, NullMetricsSink)
		state.markIdle(wID, stringset.New(0), tm1)
		a := &Assignment{
			Type:      AssignmentIdleWorker,
			WorkerID:  wID,
			RequestID: reqID,
		}
		state.applyAssignment(a)
		Convey("when AbortRequest with forward time is called for that request", func() {
			state.abortRequest(ctx, reqID, tm2)
			Convey("then the request and worker are deleted.", func() {
				So(state.queuedRequests, ShouldBeEmpty)
				So(state.workers, ShouldBeEmpty)
			})
		})
		Convey("when AbortRequest with backward time is called for that request", func() {
			state.abortRequest(ctx, reqID, tm0)
			Convey("then request should remain running on the worker.", func() {
				So(state.queuedRequests, ShouldBeEmpty)
				So(state.workers, ShouldHaveLength, 1)
				So(state.workers[wID].runningTask, ShouldNotBeNil)
				So(state.workers[wID].runningTask.request.ID, ShouldEqual, reqID)
			})
		})
	})
}

// TestApplyIdleAssignment tests that Apply for IDLE_WORKER behaves correctly.
func TestApplyIdleAssignment(t *testing.T) {
	Convey("Given a state with a task and a worker", t, func() {
		ctx := context.Background()
		s := newState(time.Unix(0, 0))
		s.addRequest(ctx, NewTaskRequest("t1", "", nil, nil, time.Unix(0, 0)), time.Unix(0, 0), NullMetricsSink)
		s.markIdle("w1", stringset.New(0), time.Unix(0, 0))

		Convey("when an idle-worker-assignment is applied with a given priority", func() {
			mut := &Assignment{Type: AssignmentIdleWorker, Priority: 1, RequestID: "t1", WorkerID: "w1"}
			s.applyAssignment(mut)
			Convey("then the state is updated as expected.", func() {
				So(s.queuedRequests, ShouldBeEmpty)
				rt := s.workers["w1"].runningTask
				So(rt, ShouldNotBeNil)
				So(rt.request.ID, ShouldEqual, "t1")
				So(rt.priority, ShouldEqual, 1)

			})
		})
	})
}

// TestApplyPreempt tests that Apply for PREEMPT_WORKER behaves correctly.
func TestApplyPreempt(t *testing.T) {
	tm := time.Unix(0, 0)
	Convey("Given a state with a running request, a queued request, and two accounts", t, func() {
		s := newState(tm)
		s.workers["w1"] = &worker{ID: "w1"}
		s.workers["w1"].runningTask = &taskRun{
			cost:     balance{1},
			priority: 2,
			request: &TaskRequest{
				ID:        "t1",
				AccountID: "a1",
			},
		}
		s.queuedRequests["t2"] = &TaskRequest{
			ID:        "t2",
			AccountID: "a2",
		}
		s.balances["a1"] = balance{1}
		s.balances["a2"] = balance{2}

		Convey("when a preemption assignment is applied", func() {
			mut := &Assignment{Type: AssignmentPreemptWorker, Priority: 1, RequestID: "t2", WorkerID: "w1", TaskToAbort: "t1"}
			s.applyAssignment(mut)

			Convey("then task queue, worker, and accounts are updated accordingly", func() {
				So(s.queuedRequests, ShouldBeEmpty)
				rt := s.workers["w1"].runningTask
				So(rt, ShouldNotBeNil)
				So(rt.cost, ShouldResemble, balance{1})
				So(rt.request.ID, ShouldEqual, "t2")
				So(s.balances["a1"], ShouldResemble, balance{2})
				So(s.balances["a2"], ShouldResemble, balance{1})
			})
		})
	})

}
