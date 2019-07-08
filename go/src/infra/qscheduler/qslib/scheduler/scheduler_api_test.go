// Copyright 2019 The LUCI Authors.
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

package scheduler_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	. "github.com/smartystreets/goconvey/convey"

	"go.chromium.org/luci/common/data/stringset"

	"infra/qscheduler/qslib/scheduler"
)

type Priority = scheduler.Priority

var FreeBucket = scheduler.FreeBucket

// TestMatchAndUnassign tests that the scheduler correctly matches
// requests with idle workers, if they are available, and that the
// Unassign call reverses this assignment.
func TestMatchAndUnassign(t *testing.T) {
	Convey("Given 2 tasks and 2 idle workers", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		w1 := scheduler.WorkerID("w1")
		w2 := scheduler.WorkerID("w2")
		r1 := scheduler.RequestID("r1")
		r2 := scheduler.RequestID("r2")
		s.MarkIdle(ctx, w1, stringset.New(0), tm, scheduler.NullEventSink)
		s.MarkIdle(ctx, w2, stringset.NewFromSlice("label1"), tm, scheduler.NullEventSink)
		s.AddRequest(ctx, scheduler.NewTaskRequest(r1, "a1", stringset.NewFromSlice("label1"), nil, tm), tm, nil, scheduler.NullEventSink)
		s.AddRequest(ctx, scheduler.NewTaskRequest(r2, "a1", stringset.NewFromSlice("label2"), nil, tm), tm, nil, scheduler.NullEventSink)
		c := scheduler.NewAccountConfig(0, 0, nil)
		s.AddAccount(ctx, "a1", c, []float32{2, 0, 0})
		Convey("when scheduling jobs", func() {
			muts := s.RunOnce(ctx, scheduler.NullEventSink)
			Convey("then both jobs should be matched, with provisionable label used as tie-breaker", func() {
				expects := []*scheduler.Assignment{
					{Type: scheduler.AssignmentIdleWorker, Priority: 0, RequestID: r1, WorkerID: w2, Time: tm},
					{Type: scheduler.AssignmentIdleWorker, Priority: 0, RequestID: r2, WorkerID: w1, Time: tm},
				}
				So(muts, ShouldResemble, expects)
				So(s.IsAssigned(r1, w2), ShouldBeTrue)
				So(s.IsAssigned(r2, w1), ShouldBeTrue)
				So(s.IsAssigned(r1, w1), ShouldBeFalse)
				So(s.IsAssigned(r2, w2), ShouldBeFalse)
			})
			Convey("then scheduling jobs again results in no new assignments.", func() {
				muts := s.RunOnce(ctx, scheduler.NullEventSink)
				So(muts, ShouldBeEmpty)
			})
			Convey("when jobs are unassigned", func() {
				err := s.Unassign(ctx, r1, w2, tm, scheduler.NullEventSink)
				So(err, ShouldBeNil)
				err = s.Unassign(ctx, r2, w1, tm, scheduler.NullEventSink)
				So(err, ShouldBeNil)
				Convey("then they are no longer assigned.", func() {
					So(s.IsAssigned(r1, w2), ShouldBeFalse)
					So(s.IsAssigned(r2, w1), ShouldBeFalse)
				})
				Convey("then they can be matched again when scheduling jobs.", func() {
					s.MarkIdle(ctx, w1, stringset.New(0), tm, scheduler.NullEventSink)
					s.MarkIdle(ctx, w2, stringset.NewFromSlice("label1"), tm, scheduler.NullEventSink)
					muts := s.RunOnce(ctx, scheduler.NullEventSink)
					So(muts, ShouldHaveLength, 2)
				})
			})
		})
	})
}

// TestMatchAccountless tests that requests without a valid account are matched at the lowest
// possible priority.
func TestMatchAccountless(t *testing.T) {
	Convey("Given a state with an idle worker", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		wid := scheduler.WorkerID("worker")
		s.MarkIdle(ctx, wid, nil, tm, scheduler.NullEventSink)

		Convey("and a request with no account", func() {
			rid := scheduler.RequestID("req")
			s.AddRequest(ctx, scheduler.NewTaskRequest(rid, "", nil, nil, tm), tm, nil, scheduler.NullEventSink)
			Convey("when scheduling is run", func() {
				muts := s.RunOnce(ctx, scheduler.NullEventSink)
				Convey("then the request is matched at lowest priority.", func() {
					So(muts, ShouldHaveLength, 1)
					So(muts[0].Priority, ShouldEqual, scheduler.FreeBucket)
					So(muts[0].RequestID, ShouldEqual, rid)
					So(muts[0].WorkerID, ShouldEqual, wid)
				})
			})
		})
	})
}

// TestMatchThrottledAccountJobs tests that scheduling logic correctly handles throttling of jobs
// that are beyond an account's max fanout, and still schedules them if there are idle workers available.
func TestMatchThrottledAccountJobs(t *testing.T) {
	Convey("Given a state with 3 idle workers, an account with a maximum fanout of 1, and 3 requests for that account (2 of which have the same provisionable labels)", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		var aid scheduler.AccountID = "Account1"
		provisionable := stringset.NewFromSlice("provisionable 1", "provisionable 2")
		s.AddAccount(ctx, aid, scheduler.NewAccountConfig(1, 0, nil), []float32{1})
		var r1 scheduler.RequestID = "SharedLabelRequest 1"
		var r2 scheduler.RequestID = "SharedLabelRequest 2"
		var r3 scheduler.RequestID = "DifferentLabelRequest"
		s.AddRequest(ctx, scheduler.NewTaskRequest(r1, aid, provisionable, nil, tm), tm, nil, scheduler.NullEventSink)
		s.AddRequest(ctx, scheduler.NewTaskRequest(r2, aid, provisionable, nil, tm), tm, nil, scheduler.NullEventSink)
		s.AddRequest(ctx, scheduler.NewTaskRequest(r3, aid, nil, nil, tm), tm, nil, scheduler.NullEventSink)
		var w1 scheduler.WorkerID = "Worker1"
		var w2 scheduler.WorkerID = "Worker2"
		var w3 scheduler.WorkerID = "Worker3"
		s.MarkIdle(ctx, w1, nil, tm, scheduler.NullEventSink)
		s.MarkIdle(ctx, w2, nil, tm, scheduler.NullEventSink)
		s.MarkIdle(ctx, w3, nil, tm, scheduler.NullEventSink)
		Convey("when running a round of scheduling", func() {
			m := s.RunOnce(ctx, scheduler.NullEventSink)
			Convey("then all 3 requests should be assigned to workers, but 1 of the shared-provisionable-label demoted to the FreeBucket priority.", func() {
				So(m, ShouldHaveLength, 3)
				priorities := make(map[scheduler.RequestID]Priority)
				counts := make(map[Priority]int)
				for _, a := range m {
					priorities[a.RequestID] = a.Priority
					counts[a.Priority]++
				}
				So(priorities[r3], ShouldEqual, 0)
				So(counts[0], ShouldEqual, 2)
				So(counts[FreeBucket], ShouldEqual, 1)
			})
		})
	})
}

// TestMatchProvisionableLabel tests that scheduler correctly matches provisionable
// label, even when a worker has more provisionable labels than tasks.
func TestMatchProvisionableLabel(t *testing.T) {
	Convey("Given 500 tasks with provisionable label 'a' and 1 task with provisionable label 'b'", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		aid := scheduler.AccountID("account1")
		reqB := scheduler.RequestID("reqb")
		s := scheduler.New(tm)
		s.AddAccount(ctx, aid, scheduler.NewAccountConfig(1, 1, nil), []float32{1})
		for i := 0; i < 500; i++ {
			id := scheduler.RequestID(fmt.Sprintf("t%d", i))
			s.AddRequest(ctx, scheduler.NewTaskRequest(id, aid, stringset.NewFromSlice("a"), nil, tm), tm, nil, scheduler.NullEventSink)
		}
		s.AddRequest(ctx, scheduler.NewTaskRequest(reqB, aid, stringset.NewFromSlice("b"), nil, tm), tm, nil, scheduler.NullEventSink)

		Convey("and an idle worker with labels 'b' and 'c'", func() {
			wid := scheduler.WorkerID("workerID")
			s.MarkIdle(ctx, wid, stringset.NewFromSlice("b", "c"), tm, scheduler.NullEventSink)

			Convey("when scheduling jobs", func() {
				muts := s.RunOnce(ctx, scheduler.NullEventSink)

				Convey("then worker is matched to the task with label 'b'.", func() {
					So(muts, ShouldHaveLength, 1)
					So(muts[0].RequestID, ShouldEqual, reqB)
					So(muts[0].WorkerID, ShouldEqual, wid)
				})
			})
		})
	})
}

func TestBaseLabelMatch(t *testing.T) {
	Convey("Given a state with 1 worker, and 1 request that has base labels not satisfied by the worker", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		var aid scheduler.AccountID = "AccountID"
		var wid scheduler.WorkerID = "WorkerID"
		var rid scheduler.RequestID = "RequestID"
		s.AddAccount(ctx, aid, scheduler.NewAccountConfig(0, 0, nil), []float32{1})
		s.MarkIdle(ctx, wid, nil, tm, scheduler.NullEventSink)
		s.AddRequest(ctx, scheduler.NewTaskRequest(rid, aid, nil, stringset.NewFromSlice("unsatisfied_label"), tm), tm, nil, scheduler.NullEventSink)
		Convey("when scheduling jobs", func() {
			m := s.RunOnce(ctx, scheduler.NullEventSink)
			Convey("no requests should be assigned to workers.", func() {
				So(m, ShouldBeEmpty)
			})
		})
	})
}

// TestMatchRareLabel tests that the worker-to-request match quality heuristics allow a rare worker to be matched
// to its corresponding rare request, even amidst other common requests that could use that worker.
func TestMatchRareLabel(t *testing.T) {
	Convey("Given a state with 10 interchangeable workers and 1 rare-labeled worker", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		commonLabel := "CommonLabel"
		for i := 0; i < 10; i++ {
			id := scheduler.WorkerID(fmt.Sprintf("CommonWorker%d", i))
			s.MarkIdle(ctx, id, stringset.NewFromSlice(commonLabel), tm, scheduler.NullEventSink)
		}
		rareLabel := "RareLabel"
		var rareWorker scheduler.WorkerID = "RareWorker"
		s.MarkIdle(ctx, rareWorker, stringset.NewFromSlice(commonLabel, rareLabel), tm, scheduler.NullEventSink)
		Convey("and 10 interchangeable requests and 1 rare-labeled request", func() {
			var aid scheduler.AccountID = "AccountID"
			s.AddAccount(ctx, aid, scheduler.NewAccountConfig(0, 0, nil), []float32{1})
			for i := 0; i < 10; i++ {
				id := scheduler.RequestID(fmt.Sprintf("CommonRequest%d", i))
				s.AddRequest(ctx, scheduler.NewTaskRequest(id, aid, nil, stringset.NewFromSlice(commonLabel), tm), tm, nil, scheduler.NullEventSink)
			}
			var rareRequest scheduler.RequestID = "RareRequest"
			s.AddRequest(ctx, scheduler.NewTaskRequest(rareRequest, aid, nil, stringset.NewFromSlice(commonLabel, rareLabel), tm), tm, nil, scheduler.NullEventSink)
			Convey("when scheduling jobs", func() {
				muts := s.RunOnce(ctx, scheduler.NullEventSink)
				Convey("then all jobs are scheduled to workers, including the rare requests and workers.", func() {
					So(muts, ShouldHaveLength, 11)
					So(s.IsAssigned(rareRequest, rareWorker), ShouldBeTrue)
				})
			})
		})
	})
}

// TestAddRequest ensures that AddRequest enqueues a request.
func TestAddRequest(t *testing.T) {
	ctx := context.Background()
	tm := time.Unix(0, 0)
	s := scheduler.New(tm)
	r := scheduler.NewTaskRequest("r1", "a1", nil, nil, tm)
	s.AddRequest(ctx, r, tm, nil, scheduler.NullEventSink)

	if _, ok := s.GetRequest("r1"); !ok {
		t.Errorf("AddRequest did not enqueue request.")
	}
}

func TestExpireWorker(t *testing.T) {
	Convey("Given an empty scheduler, with an an idle worker", t, func() {
		ctx := context.Background()
		tm := time.Unix(0, 0)
		s := scheduler.New(tm)
		s.MarkIdle(ctx, "worker1", nil, tm, scheduler.NullEventSink)
		So(s.GetWorkers(), ShouldHaveLength, 1)
		Convey("when time is updated by less than expiry threshold, worker is still idle.", func() {
			t2 := tm.Add(150 * time.Second)
			s.UpdateTime(ctx, t2)
			So(s.GetWorkers(), ShouldHaveLength, 1)
		})
		Convey("when time is updated by more than expiry threshold, worker is removed.", func() {
			t2 := tm.Add(301 * time.Second)
			s.UpdateTime(ctx, t2)
			So(s.GetWorkers(), ShouldBeEmpty)
		})
	})
}
