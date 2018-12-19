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
	"fmt"
	"reflect"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"
)

// TestMatchWithIdleWorkers tests that the scheduler correctly matches
// requests with idle workers, if they are available.
func TestMatchWithIdleWorkers(t *testing.T) {
	Convey("Given 2 tasks and 2 idle workers", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := New(tm)
		s.MarkIdle(ctx, "w0", []string{}, tm)
		s.MarkIdle(ctx, "w1", []string{"label1"}, tm)
		s.AddRequest(ctx, "t1", NewRequest("a1", []string{"label1"}, tm), tm)
		s.AddRequest(ctx, "t2", NewRequest("a1", []string{"label2"}, tm), tm)
		c := NewAccountConfig(0, 0, nil)
		s.AddAccount(ctx, "a1", c, []float64{2, 0, 0})
		Convey("when scheduling jobs", func() {
			muts, _ := s.RunOnce(ctx)
			Convey("then both jobs should be matched, with provisionable label used as tie-breaker", func() {
				expects := []*Assignment{
					{Type: AssignmentIdleWorker, Priority: 0, RequestID: "t1", WorkerID: "w1", Time: tm},
					{Type: AssignmentIdleWorker, Priority: 0, RequestID: "t2", WorkerID: "w0", Time: tm},
				}
				So(muts, ShouldResemble, expects)
			})
		})
	})
}

// TestMatchProvisionableLabel tests that scheduler correctly matches provisionable
// label, even when a worker has more provisionable labels than tasks.
func TestMatchProvisionableLabel(t *testing.T) {
	Convey("Given 500 tasks with label 'a' and 1 task with label 'b'", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := New(tm)
		for i := 0; i < 500; i++ {
			id := fmt.Sprintf("t%d", i)
			s.AddRequest(ctx, id, NewRequest("", []string{"a"}, tm), tm)
		}
		s.AddRequest(ctx, "tb", NewRequest("", []string{"b"}, tm), tm)

		Convey("and an idle worker with labels 'b' and 'c'", func() {
			s.MarkIdle(ctx, "wb", []string{"b", "c"}, tm)

			Convey("when scheduling jobs", func() {
				muts, _ := s.RunOnce(ctx)

				Convey("then worker is matched to the task with label 'b'.", func() {
					So(muts, ShouldHaveLength, 1)
					So(muts[0].RequestID, ShouldEqual, "tb")
					So(muts[0].WorkerID, ShouldEqual, "wb")
				})
			})
		})
	})
}

// TestReprioritize tests that the scheduler correctly changes the priority
// of running jobs (promote or demote) if the account balance makes that
// necessary.
func TestSchedulerReprioritize(t *testing.T) {
	// Prepare a situation in which one P0 job (out of 2 running) will be
	// demoted, and a separate P2 job will be promoted to P1.
	Convey("Given two running requests with different costs for an account that needs 1 demotion from P0, and supports 1 additional P1 job", t, func() {
		ctx := context.Background()
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		aid := "a1"
		s.config.AccountConfigs[aid] = &AccountConfig{ChargeRate: []float64{1.1, 0.9}}
		s.state.balances[aid] = balance{2 * DemoteThreshold, 2 * PromoteThreshold, 0}

		for _, i := range []int{1, 2} {
			rid := fmt.Sprintf("r%d", i)
			wid := fmt.Sprintf("w%d", i)
			addRunningRequest(ctx, s, rid, wid, aid, 0, tm0)
		}
		s.state.workers["w2"].runningTask.cost = balance{1, 0, 0}

		Convey("given both requests running at P0", func() {
			Convey("when scheduling", func() {
				s.RunOnce(ctx)
				Convey("then the cheaper request should be demoted.", func() {
					So(s.state.workers["w1"].runningTask.priority, ShouldEqual, 1)
					So(s.state.workers["w2"].runningTask.priority, ShouldEqual, 0)
				})
			})
		})

		Convey("given both requests running at P2", func() {
			for _, wid := range []string{"w1", "w2"} {
				s.state.workers[wid].runningTask.priority = 2
			}
			Convey("when scheduling", func() {

				s.RunOnce(ctx)
				Convey("then the more expensive should be promoted.", func() {
					So(s.state.workers["w1"].runningTask.priority, ShouldEqual, 2)
					So(s.state.workers["w2"].runningTask.priority, ShouldEqual, 1)
				})
			})
		})
	})
}

// TestPreempt tests that the scheduler correctly preempts lower priority jobs
// running on a worker, when a higher priority job appears to take its place.
func TestSchedulerPreempt(t *testing.T) {
	Convey("Given a state with two running P1 tasks", t, func() {
		ctx := context.Background()
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		s.AddAccount(ctx, "a1", NewAccountConfig(0, 0, []float64{1, 1, 1}), []float64{0.5 * PromoteThreshold, 1})
		for _, i := range []int{1, 2} {
			rid := fmt.Sprintf("r%d", i)
			wid := fmt.Sprintf("w%d", i)
			s.AddRequest(ctx, rid, NewRequest("a1", nil, tm0), tm0)
			s.MarkIdle(ctx, wid, []string{}, tm0)
			s.state.applyAssignment(&Assignment{RequestID: rid, WorkerID: wid, Type: AssignmentIdleWorker, Priority: 1})
		}
		s.state.workers["w1"].runningTask.cost = balance{0, 1, 0}
		Convey("given a new P0 request from a different account", func() {
			s.AddAccount(ctx, "a2", NewAccountConfig(0, 0, nil), nil)
			s.AddRequest(ctx, "r3", NewRequest("a2", nil, tm0), tm0)
			Convey("given sufficient balance", func() {
				s.state.balances["a2"] = balance{1}
				Convey("when scheduling", func() {
					tm1 := time.Unix(1, 0)
					s.UpdateTime(ctx, tm1)
					got, _ := s.RunOnce(ctx)
					Convey("then the cheaper running job is preempted.", func() {
						want := &Assignment{Type: AssignmentPreemptWorker, Priority: 0, WorkerID: "w2", RequestID: "r3", TaskToAbort: "r2", Time: tm1}
						So(got, ShouldResemble, []*Assignment{want})
					})
				})
			})
			Convey("given insufficient balance", func() {
				Convey("when scheduling", func() {
					got, _ := s.RunOnce(ctx)
					Convey("then nothing happens.", func() {
						So(got, ShouldBeEmpty)
					})
				})
			})
		})

		Convey("given a new P0 request from the same account", func() {
			s.AddRequest(ctx, "r3", NewRequest("a1", nil, tm0), tm0)
			Convey("when scheduling", func() {
				got, _ := s.RunOnce(ctx)
				Convey("then nothing happens.", func() {
					So(got, ShouldBeEmpty)
				})
			})
		})
	})
}

// TestUpdateErrors test that UpdateBalance returns the correct errors
// under error conditions.
func TestUpdateErrors(t *testing.T) {
	ctx := context.Background()
	cases := []struct {
		S      *Scheduler
		T      time.Time
		Expect error
	}{
		{
			// Force UTC time representation, so that we get a predictable error
			// message that we can assert on.
			&Scheduler{
				state:  newState(time.Unix(100, 0).UTC()),
				config: NewConfig(),
			},
			time.Unix(0, 0).UTC(),
			&UpdateOrderError{Next: time.Unix(0, 0).UTC(), Previous: time.Unix(100, 0).UTC()},
		},
		{
			&Scheduler{
				state:  newState(time.Unix(0, 0)),
				config: NewConfig(),
			},
			time.Unix(1, 0),
			nil,
		},
	}

	for i, test := range cases {
		e := test.S.UpdateTime(ctx, test.T)
		if !reflect.DeepEqual(e, test.Expect) {
			t.Errorf("In case %d, got error: %+v, want error: %+v", i, e, test.Expect)
		}
	}
}

// TestUpdateBalance tests that UpdateBalance makes the correct modifications
// to account balances and task run costs.
func TestUpdateBalance(t *testing.T) {
	t0 := time.Unix(0, 0)
	aID := "accountID"
	Convey("Given a scheduler with an added account config", t, func() {
		ctx := context.Background()
		s := New(t0)
		maxTime := 2.0
		s.AddAccount(ctx, aID, NewAccountConfig(0, maxTime, []float64{1, 2, 3}), nil)

		Convey("then a zeroed balance for that account exists", func() {
			So(s.state.balances, ShouldContainKey, aID)
			So(s.state.balances[aID], ShouldResemble, balance{})
		})

		Convey("when updating time forward", func() {
			t1 := t0.Add(time.Second)
			s.UpdateTime(ctx, t1)
			Convey("then account balance should be increased according to charge rate", func() {
				So(s.state.balances[aID], ShouldResemble, balance{1, 2, 3})
			})
		})

		Convey("when updating time forward beyond the account's max charge time", func() {
			t1 := t0.Add(10 * time.Second)
			s.UpdateTime(ctx, t1)
			Convey("then account balance saturates at the maximum charge.", func() {
				So(s.state.balances[aID], ShouldResemble, balance{2, 4, 6})
			})
		})

		Convey("when account config is removed", func() {
			delete(s.config.AccountConfigs, aID)
			Convey("when updating time forward", func() {
				t1 := t0.Add(time.Second)
				s.UpdateTime(ctx, t1)
				Convey("then account balance is absent.", func() {
					So(s.state.balances, ShouldNotContainKey, aID)
				})
			})
		})

		Convey("when 2 tasks for the account are running", func() {
			r1 := "request 1"
			r2 := "request 2"
			s.AddRequest(ctx, r1, newTaskRequest(&request{aID, t0, nil, t0}), t0)
			s.AddRequest(ctx, r2, newTaskRequest(&request{aID, t0, nil, t0}), t0)
			s.MarkIdle(ctx, "w1", nil, t0)
			s.MarkIdle(ctx, "w2", nil, t0)
			s.state.applyAssignment(&Assignment{Priority: 0, RequestID: r1, WorkerID: "w1", Type: AssignmentIdleWorker})
			s.state.applyAssignment(&Assignment{Priority: 0, RequestID: r2, WorkerID: "w2", Type: AssignmentIdleWorker})
			So(s.state.queuedRequests, ShouldBeEmpty)
			So(s.state.workers, ShouldHaveLength, 2)
			Convey("when updating time forward", func() {
				t1 := t0.Add(time.Second)
				s.UpdateTime(ctx, t1)
				Convey("then account balance reflects charges for running tasks.", func() {
					So(s.state.balances[aID], ShouldResemble, balance{-1, 2, 3})
				})
			})
		})
	})

}

// TestAddRequest ensures that AddRequest enqueues a request.
func TestAddRequest(t *testing.T) {
	ctx := context.Background()
	tm := time.Unix(0, 0)
	s := New(tm)
	r := NewRequest("a1", nil, tm)
	s.AddRequest(ctx, "r1", r, tm)
	if _, ok := s.state.queuedRequests["r1"]; !ok {
		t.Errorf("AddRequest did not enqueue request.")
	}
}
