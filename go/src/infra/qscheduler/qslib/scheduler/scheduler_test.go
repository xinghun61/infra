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
	"errors"
	"fmt"
	"reflect"
	"testing"
	"time"

	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/task"
	"infra/qscheduler/qslib/types/vector"

	"github.com/kylelemons/godebug/pretty"
)

// TestMatchWithIdleWorkers tests that the scheduler correctly matches
// requests with idle workers, if they are available.
func TestMatchWithIdleWorkers(t *testing.T) {
	t.Parallel()
	s := &Scheduler{
		&State{
			Workers: map[string]*Worker{
				"w0": NewWorker(),
				"w1": &Worker{Labels: []string{"label1"}},
			},
			Requests: map[string]*task.Request{
				"t1": &task.Request{AccountId: "a1", Labels: []string{"label1"}},
				"t2": &task.Request{AccountId: "a1", Labels: []string{"label2"}},
			},
			Balances: map[string]*vector.Vector{
				"a1": vector.New(2, 0, 0),
			},
		},
		&Config{
			AccountConfigs: map[string]*account.Config{
				"a1": account.NewConfig(),
			},
		},
	}

	expects := []*Assignment{
		&Assignment{Type: Assignment_IDLE_WORKER, Priority: 0, RequestId: "t1", WorkerId: "w1"},
		&Assignment{Type: Assignment_IDLE_WORKER, Priority: 0, RequestId: "t2", WorkerId: "w0"},
	}

	muts := s.RunOnce()

	if diff := pretty.Compare(muts, expects); diff != "" {
		t.Errorf(fmt.Sprintf("Unexpected mutations diff (-got +want): %s", diff))
	}
}

// TestReprioritize tests that the scheduler correctly changes the priority
// of running jobs (promote or demote) if the account balance makes that
// necessary.
func TestSchedulerReprioritize(t *testing.T) {
	t.Parallel()
	// Prepare a situation in which one P0 job (out of 2 running) will be
	// demoted, and a separate P2 job will be promoted to P1.
	s := &Scheduler{
		&State{
			Balances: map[string]*vector.Vector{
				"a1": vector.New(2*account.DemoteThreshold, 2*account.PromoteThreshold, 0),
			},
			Workers: map[string]*Worker{
				"w1": &Worker{
					RunningTask: &task.Run{
						Cost:     vector.New(1),
						Priority: 0,
						Request:  &task.Request{AccountId: "a1"},
					},
				},
				"w2": &Worker{
					RunningTask: &task.Run{
						Priority: 0,
						Request:  &task.Request{AccountId: "a1"},
						Cost:     vector.New(),
					},
				},
				"w3": &Worker{
					RunningTask: &task.Run{
						Cost:     vector.New(1),
						Priority: 2,
						Request:  &task.Request{AccountId: "a1"},
					},
				},
				"w4": &Worker{
					RunningTask: &task.Run{
						Priority: 2,
						Request:  &task.Request{AccountId: "a1"},
						Cost:     vector.New(),
					},
				},
			},
		},
		&Config{
			AccountConfigs: map[string]*account.Config{
				"a1": &account.Config{ChargeRate: vector.New(1.5, 1.5)},
			},
		},
	}

	expects := s.state.Clone()
	expects.Workers["w2"].RunningTask.Priority = 1
	expects.Workers["w3"].RunningTask.Priority = 1

	muts := s.RunOnce()

	if len(muts) != 0 {
		t.Errorf("Unexpected muts, got %s want {}", muts)
	}

	if diff := pretty.Compare(s.state, expects); diff != "" {
		t.Errorf(fmt.Sprintf("Unexpected state diff (-got +want): %s", diff))
	}
}

// TestPreempt tests that the scheduler correctly preempts lower priority jobs
// running on a worker, when a higher priority job appears to take its place.
func TestSchedulerPreempt(t *testing.T) {
	t.Parallel()
	cases := []struct {
		S      *Scheduler
		Expect []*Assignment
	}{
		// Case 0
		//
		// Basic preemption of a job by a higher priority job.
		{
			&Scheduler{
				&State{
					Balances: map[string]*vector.Vector{
						"a1": vector.New(),
						"a2": vector.New(1),
					},
					Requests: map[string]*task.Request{
						"t1": &task.Request{AccountId: "a2"},
					},
					Workers: map[string]*Worker{
						"w1": &Worker{
							RunningTask: &task.Run{
								Cost:      vector.New(.5, .5, .5),
								Priority:  1,
								Request:   &task.Request{AccountId: "a1"},
								RequestId: "t2",
							},
						},
					},
				},
				&Config{
					AccountConfigs: map[string]*account.Config{
						"a1": account.NewConfig(),
						"a2": account.NewConfig(),
					},
				},
			},
			[]*Assignment{
				&Assignment{Type: Assignment_PREEMPT_WORKER, Priority: 0, WorkerId: "w1", RequestId: "t1"},
			},
		},
		// Case 1
		//
		// Preemption will be skipped if:
		// - the preempting account has insufficient funds.
		// - the preempting account already has lower priority jobs.
		{
			&Scheduler{
				&State{
					// Both accounts a1 and a2 have P0 quota.
					Balances: map[string]*vector.Vector{
						// a1 has insufficient balance to preempt jobs.
						"a1": vector.New(0.1 * account.PromoteThreshold),
						// a2 would have sufficient balance to preempt jobs, but has
						// insufficient balance to promote its already running job, and
						// thus is banned from preempting jobs.
						"a2": vector.New(0.9 * account.PromoteThreshold),
					},
					Requests: map[string]*task.Request{
						"t1": &task.Request{AccountId: "a1"},
						"t2": &task.Request{AccountId: "a2"},
					},
					Workers: map[string]*Worker{
						// A job is running, but it is too costly for a1 to preempt.
						"w1": &Worker{
							RunningTask: &task.Run{
								Cost:      vector.New(0.5*account.PromoteThreshold, 0, 0),
								Priority:  1,
								Request:   &task.Request{},
								RequestId: "other_req",
							},
						},
						// A job is running for a2 at a lower priority, so a2 is banned
						// from preempting jobs.
						"w2": &Worker{
							RunningTask: &task.Run{
								Cost:      vector.New(0.5 * account.PromoteThreshold),
								Priority:  1,
								Request:   &task.Request{AccountId: "a2"},
								RequestId: "t3",
							},
						},
					},
				},
				&Config{
					AccountConfigs: map[string]*account.Config{
						"a1": &account.Config{ChargeRate: vector.New(1)},
						"a2": &account.Config{ChargeRate: vector.New(1)},
					},
				},
			},
			// No preemptions or other mutations should result.
			[]*Assignment{},
		},
	}

	for i, test := range cases {
		actual := test.S.RunOnce()
		if diff := pretty.Compare(actual, test.Expect); diff != "" {
			t.Errorf(fmt.Sprintf("Case %d, unexpected mutations diff (-got +want): %s", i, diff))
		}
	}
}

// TestUpdateErrors test that UpdateBalance returns the correct errors
// under error conditions.
func TestUpdateErrors(t *testing.T) {
	cases := []struct {
		S      *Scheduler
		T      time.Time
		Expect error
	}{
		{
			&Scheduler{
				NewState(),
				NewConfig(),
			},
			time.Unix(0, 0),
			errors.New("timestamp: nil Timestamp"),
		},
		{
			&Scheduler{
				stateAtTime(time.Unix(100, 0).UTC()),
				NewConfig(),
			},
			time.Unix(0, 0).UTC(),
			&UpdateOrderError{Next: time.Unix(0, 0).UTC(), Previous: time.Unix(100, 0).UTC()},
		},
		{
			&Scheduler{
				stateAtTime(time.Unix(0, 0)),
				NewConfig(),
			},
			time.Unix(1, 0),
			nil,
		},
	}

	for i, test := range cases {
		e := test.S.UpdateTime(test.T)
		if !reflect.DeepEqual(e, test.Expect) {
			t.Errorf("In case %d, got error: %+v, want error: %+v", i, e, test.Expect)
		}
	}
}

// TestUpdateBalance tests that UpdateBalance makes the correct modifications
// to account balances and task run costs.
func TestUpdateBalance(t *testing.T) {
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
					"a2": &account.Config{ChargeRate: vector.New(1), MaxChargeSeconds: 2},
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
					"w1": &Worker{
						RunningTask: &task.Run{
							Cost:     vector.New(1),
							Priority: 1,
							Request:  &task.Request{AccountId: "a1"},
						},
					},
					// Worker running a task with uninitialized Cost.
					"w2": &Worker{
						RunningTask: &task.Run{
							Priority: 2,
							Request:  &task.Request{AccountId: "a1"},
						},
					},
					// Worker running a task with invalid account.
					"w3": &Worker{
						RunningTask: &task.Run{
							Priority: account.FreeBucket,
							Request:  &task.Request{AccountId: "a2"},
						},
					},
				},
				LastUpdateTime: t0,
			},
			&Config{
				AccountConfigs: map[string]*account.Config{
					"a1": &account.Config{ChargeRate: vector.New(1), MaxChargeSeconds: 1},
				},
			},
			epoch.Add(2 * time.Second),
			&State{
				Balances:       map[string]*vector.Vector{"a1": vector.New(1, -2, -2)},
				LastUpdateTime: t2,
				Workers: map[string]*Worker{
					"w1": &Worker{
						RunningTask: &task.Run{
							Cost:     vector.New(1, 2),
							Priority: 1,
							Request:  &task.Request{AccountId: "a1"},
						},
					},
					"w2": &Worker{
						RunningTask: &task.Run{
							Cost:     vector.New(0, 0, 2),
							Priority: 2,
							Request:  &task.Request{AccountId: "a1"},
						},
					},
					"w3": &Worker{
						RunningTask: &task.Run{
							Cost:     vector.New(),
							Priority: account.FreeBucket,
							Request:  &task.Request{AccountId: "a2"},
						},
					},
				},
			},
		},
	}

	for i, test := range cases {
		actual := test.State
		(&Scheduler{test.State, test.Config}).UpdateTime(test.T)
		if diff := pretty.Compare(actual, test.Expect); diff != "" {
			t.Errorf(fmt.Sprintf("Case %d unexpected mutations diff (-got +want): %s", i, diff))
		}
	}
}

// stateAtTime is a testing helper that creates an initialized but empty
//  State instance with the given time as its LastAccountUpdate time.
func stateAtTime(t time.Time) *State {
	s := NewState()
	s.LastUpdateTime = tutils.TimestampProto(t)
	return s
}
