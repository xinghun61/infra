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
	"errors"
	"fmt"
	"reflect"
	"testing"
	"time"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/vector"

	"github.com/kylelemons/godebug/pretty"

	. "github.com/smartystreets/goconvey/convey"
)

// TestMatchWithIdleWorkers tests that the scheduler correctly matches
// requests with idle workers, if they are available.
func TestMatchWithIdleWorkers(t *testing.T) {
	ctx := context.Background()
	Convey("Given 2 tasks and 2 idle workers", t, func() {
		tm := time.Unix(0, 0)
		s := New(tm)
		s.MarkIdle(ctx, "w0", []string{}, tm)
		s.MarkIdle(ctx, "w1", []string{"label1"}, tm)
		s.AddRequest(ctx, "t1", NewRequest("a1", []string{"label1"}, tm), tm)
		s.AddRequest(ctx, "t2", NewRequest("a1", []string{"label2"}, tm), tm)
		c := account.NewConfig(0, 0, vector.New())
		s.AddAccount(ctx, "a1", c, vector.New(2, 0, 0))
		Convey("when scheduling jobs", func() {
			muts, _ := s.RunOnce(ctx)
			Convey("then both jobs should be matched, with provisionable label used as tie-breaker", func() {
				tmproto := tutils.TimestampProto(tm)
				expects := []*Assignment{
					{Type: Assignment_IDLE_WORKER, Priority: 0, RequestId: "t1", WorkerId: "w1", Time: tmproto},
					{Type: Assignment_IDLE_WORKER, Priority: 0, RequestId: "t2", WorkerId: "w0", Time: tmproto},
				}
				So(muts, shouldResemblePretty, expects)
			})
		})
	})
}

// TestReprioritize tests that the scheduler correctly changes the priority
// of running jobs (promote or demote) if the account balance makes that
// necessary.
func TestSchedulerReprioritize(t *testing.T) {
	ctx := context.Background()
	// Prepare a situation in which one P0 job (out of 2 running) will be
	// demoted, and a separate P2 job will be promoted to P1.
	Convey("Given two running requests with different costs for an account that needs 1 demotion from P0, and supports 1 additional P1 job", t, func() {
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		aid := "a1"
		s.Config.AccountConfigs[aid] = &account.Config{ChargeRate: vector.New(1.1, 0.9)}
		s.State.Balances[aid] = vector.New(2*account.DemoteThreshold, 2*account.PromoteThreshold, 0)

		for _, i := range []int{1, 2} {
			rid := fmt.Sprintf("r%d", i)
			wid := fmt.Sprintf("w%d", i)
			addRunningRequest(ctx, s, rid, wid, aid, 0, tm0)
		}
		s.State.Workers["w2"].RunningTask.Cost = vector.New(1)

		Convey("given both requests running at P0", func() {
			Convey("when scheduling", func() {
				s.RunOnce(ctx)
				Convey("then the cheaper request should be demoted.", func() {
					So(s.State.Workers["w1"].RunningTask.Priority, ShouldEqual, 1)
					So(s.State.Workers["w2"].RunningTask.Priority, ShouldEqual, 0)
				})
			})
		})

		Convey("given both requests running at P2", func() {
			for _, wid := range []string{"w1", "w2"} {
				s.State.Workers[wid].RunningTask.Priority = 2
			}
			Convey("when scheduling", func() {

				s.RunOnce(ctx)
				Convey("then the more expensive should be promoted.", func() {
					So(s.State.Workers["w1"].RunningTask.Priority, ShouldEqual, 2)
					So(s.State.Workers["w2"].RunningTask.Priority, ShouldEqual, 1)
				})
			})
		})
	})
}

// TestPreempt tests that the scheduler correctly preempts lower priority jobs
// running on a worker, when a higher priority job appears to take its place.
func TestSchedulerPreempt(t *testing.T) {
	ctx := context.Background()
	Convey("Given a state with two running P1 tasks", t, func() {
		tm0 := time.Unix(0, 0)
		s := New(tm0)
		s.AddAccount(ctx, "a1", account.NewConfig(0, 0, vector.New(1, 1, 1)), vector.New(0.5*account.PromoteThreshold, 1))
		for _, i := range []int{1, 2} {
			rid := fmt.Sprintf("r%d", i)
			wid := fmt.Sprintf("w%d", i)
			s.AddRequest(ctx, rid, NewRequest("a1", nil, tm0), tm0)
			s.MarkIdle(ctx, wid, []string{}, tm0)
			s.State.applyAssignment(&Assignment{RequestId: rid, WorkerId: wid, Type: Assignment_IDLE_WORKER, Priority: 1})
		}
		s.State.Workers["w1"].RunningTask.Cost = vector.New(0, 1)
		Convey("given a new P0 request from a different account", func() {
			s.AddAccount(ctx, "a2", account.NewConfig(0, 0, vector.New()), vector.New())
			s.AddRequest(ctx, "r3", NewRequest("a2", nil, tm0), tm0)
			Convey("given sufficient balance", func() {
				s.State.Balances["a2"] = vector.New(1)
				Convey("when scheduling", func() {
					tm1 := time.Unix(1, 0)
					s.UpdateTime(ctx, tm1)
					got, _ := s.RunOnce(ctx)
					Convey("then the cheaper running job is preempted.", func() {
						want := &Assignment{Type: Assignment_PREEMPT_WORKER, Priority: 0, WorkerId: "w2", RequestId: "r3", TaskToAbort: "r2", Time: tutils.TimestampProto(tm1)}
						So(got, shouldResemblePretty, []*Assignment{want})
					})
				})
			})
			Convey("given insufficient balance", func() {
				stateBefore := s.State.Clone()
				Convey("when scheduling", func() {
					got, _ := s.RunOnce(ctx)
					Convey("then nothing happens.", func() {
						So(got, ShouldBeEmpty)
						So(s.State, shouldResemblePretty, stateBefore)
					})
				})
			})
		})

		Convey("given a new P0 request from the same account", func() {
			s.AddRequest(ctx, "r3", NewRequest("a1", nil, tm0), tm0)
			stateBefore := s.State.Clone()
			Convey("when scheduling", func() {
				got, _ := s.RunOnce(ctx)
				Convey("then nothing happens.", func() {
					So(got, ShouldBeEmpty)
					So(s.State, shouldResemblePretty, stateBefore)
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
			&Scheduler{
				State:  &State{},
				Config: &Config{},
			},
			time.Unix(0, 0),
			errors.New("timestamp: nil Timestamp"),
		},
		{
			// Force UTC time representation, so that we get a predictable error
			// message that we can assert on.
			&Scheduler{
				State:  NewState(time.Unix(100, 0).UTC()),
				Config: NewConfig(),
			},
			time.Unix(0, 0).UTC(),
			&UpdateOrderError{Next: time.Unix(0, 0).UTC(), Previous: time.Unix(100, 0).UTC()},
		},
		{
			&Scheduler{
				State:  NewState(time.Unix(0, 0)),
				Config: NewConfig(),
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
	ctx := context.Background()
	epoch := time.Unix(0, 0)
	t0 := tutils.TimestampProto(epoch)
	t1 := tutils.TimestampProto(epoch.Add(1 * time.Second))
	t2 := tutils.TimestampProto(epoch.Add(2 * time.Second))

	cases := []struct {
		State  *State
		Config *Config
		T      time.Time
		Expect *State
	}{
		// Case 0:
		// Balances with no account config should be removed ("a1"). New balances
		// should be created if necessary and incremented appropriately ("a2").
		{
			&State{
				Balances:       map[string]*vector.Vector{"a1": vector.New()},
				LastUpdateTime: t0,
			},
			&Config{
				AccountConfigs: map[string]*account.Config{
					"a2": {ChargeRate: vector.New(1), MaxChargeSeconds: 2},
				},
			},
			epoch.Add(1 * time.Second),
			&State{
				Balances:       map[string]*vector.Vector{"a2": vector.New(1)},
				LastUpdateTime: t1,
			},
		},
		// Case 1:
		// Running jobs should count against the account. Cost of a running job
		// should be initialized if necessary, and incremented.
		//
		// Charges should be proportional to time advanced (2 seconds in this case).
		{
			&State{
				Balances: map[string]*vector.Vector{"a1": vector.New()},
				Workers: map[string]*Worker{
					// Worker running a task.
					"w1": {
						RunningTask: &TaskRun{
							Cost:     vector.New(1),
							Priority: 1,
							Request:  NewRequest("a1", nil, epoch),
						},
					},
					// Worker running a task with uninitialized Cost.
					"w2": {
						RunningTask: &TaskRun{
							Priority: 2,
							Request:  NewRequest("a1", nil, epoch),
						},
					},
					// Worker running a task with invalid account.
					"w3": {
						RunningTask: &TaskRun{
							Priority: account.FreeBucket,
							Request:  NewRequest("a2", nil, epoch),
						},
					},
				},
				LastUpdateTime: t0,
			},
			&Config{
				AccountConfigs: map[string]*account.Config{
					"a1": {ChargeRate: vector.New(1), MaxChargeSeconds: 1},
				},
			},
			epoch.Add(2 * time.Second),
			&State{
				Balances:       map[string]*vector.Vector{"a1": vector.New(1, -2, -2)},
				LastUpdateTime: t2,
				Workers: map[string]*Worker{
					"w1": {
						RunningTask: &TaskRun{
							Cost:     vector.New(1, 2),
							Priority: 1,
							Request:  NewRequest("a1", nil, epoch),
						},
					},
					"w2": {
						RunningTask: &TaskRun{
							Cost:     vector.New(0, 0, 2),
							Priority: 2,
							Request:  NewRequest("a1", nil, epoch),
						},
					},
					"w3": {
						RunningTask: &TaskRun{
							Cost:     vector.New(),
							Priority: account.FreeBucket,
							Request:  NewRequest("a2", nil, epoch),
						},
					},
				},
			},
		},
	}

	for i, test := range cases {
		actual := test.State
		(&Scheduler{State: test.State, Config: test.Config}).UpdateTime(ctx, test.T)
		if diff := pretty.Compare(actual, test.Expect); diff != "" {
			t.Errorf(fmt.Sprintf("Case %d unexpected mutations diff (-got +want): %s", i, diff))
		}
	}
}

// TestAddRequest ensures that AddRequest enqueues a request.
func TestAddRequest(t *testing.T) {
	ctx := context.Background()
	tm := time.Unix(0, 0)
	s := New(tm)
	r := NewRequest("a1", nil, tm)
	s.AddRequest(ctx, "r1", r, tm)
	if s.State.QueuedRequests["r1"] != r {
		t.Errorf("AddRequest did not enqueue request.")
	}
}
