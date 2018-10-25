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

package reconciler

import (
	"context"
	"fmt"
	"testing"
	"time"

	"infra/qscheduler/qslib/scheduler"
	"infra/qscheduler/qslib/tutils"
	"infra/qscheduler/qslib/types/account"
	"infra/qscheduler/qslib/types/vector"

	"github.com/kylelemons/godebug/pretty"

	. "github.com/smartystreets/goconvey/convey"
)

// TestQuotaschedulerInterface ensures that scheduler.Scheduler is a valid
// implementation of the Scheduler interface.
func TestQuotaschedulerInterface(t *testing.T) {
	var s interface{} = &scheduler.Scheduler{}
	if _, ok := s.(Scheduler); !ok {
		t.Errorf("Scheduler interface should be implemented by *scheduler.Scheduler")
	}
}

func assertAssignments(t *testing.T, description string,
	got []Assignment, want []Assignment) {
	t.Helper()
	if diff := pretty.Compare(got, want); diff != "" {
		t.Errorf(fmt.Sprintf("%s got unexpected assignment diff (-got +want): %s", description, diff))
	}
}

// TestOneAssignment tests that a scheduler assignment for a single idle
// worker is correctly assigned, and that subsequent calls after Notify
// return the correct results.
func TestOneAssignment(t *testing.T) {
	ctx := context.Background()
	Convey("Given an empty scheduler and reconciler state", t, func() {
		t0 := time.Unix(0, 0)
		t1 := time.Unix(1, 0)
		t2 := time.Unix(2, 0)
		s := scheduler.New(t0)
		r := New()

		Convey("given an idle task has been notified", func() {
			aid := "Account1"
			labels := []string{"Label1"}
			rid := "Request1"
			taskUpdate := &TaskUpdate{
				AccountId:           aid,
				ProvisionableLabels: labels,
				RequestId:           rid,
				Type:                TaskUpdate_NEW,
				Time:                tutils.TimestampProto(t0),
				EnqueueTime:         tutils.TimestampProto(t0),
			}

			r.Notify(ctx, s, taskUpdate)

			Convey("when AssignTasks is called for a worker", func() {
				wid := "Worker1"
				as := r.AssignTasks(ctx, s, t0, &IdleWorker{ID: wid})

				Convey("then it is given the assigned task.", func() {
					So(as, ShouldHaveLength, 1)
					a := as[0]
					So(a.RequestID, ShouldEqual, rid)
					So(a.WorkerID, ShouldEqual, wid)
				})

				Convey("when AssignTasks is called again for the same worker", func() {
					as = r.AssignTasks(ctx, s, t1, &IdleWorker{ID: wid})
					Convey("then it is given the same task.", func() {
						So(as, ShouldHaveLength, 1)
						a := as[0]
						So(a.RequestID, ShouldEqual, rid)
						So(a.WorkerID, ShouldEqual, wid)
					})
				})

				matchingNotifyCases := []struct {
					desc string
					t    time.Time
				}{
					{
						"at a future time",
						t1,
					},
					{
						"at the same time",
						t0,
					},
				}
				for _, c := range matchingNotifyCases {
					Convey(fmt.Sprintf("when the task is notified on the worker %s", c.desc), func() {
						taskUpdate := &TaskUpdate{
							RequestId: rid,
							WorkerId:  wid,
							Type:      TaskUpdate_ASSIGNED,
							Time:      tutils.TimestampProto(c.t),
						}
						r.Notify(ctx, s, taskUpdate)

						Convey("when AssignTasks is called again for the same worker", func() {
							as = r.AssignTasks(ctx, s, t2, &IdleWorker{ID: wid})
							Convey("then it is no longer given the task.", func() {
								So(as, ShouldBeEmpty)
							})
						})
					})
				}

				Convey("when a different task is notified on the worker", func() {
					rid2 := "Request2"
					taskUpdate := &TaskUpdate{
						RequestId: rid2,
						WorkerId:  wid,
						Type:      TaskUpdate_ASSIGNED,
						Time:      tutils.TimestampProto(t1),
					}
					r.Notify(ctx, s, taskUpdate)

					Convey("when AssignTasks is called again for the same worker", func() {
						as = r.AssignTasks(ctx, s, t2, &IdleWorker{ID: wid})
						Convey("then it is no longer given the task.", func() {
							So(as, ShouldBeEmpty)
						})
					})
				})

				Convey("when the task is notified on a different worker", func() {
					wid2 := "Worker2"
					taskUpdate := &TaskUpdate{
						RequestId: rid,
						WorkerId:  wid2,
						Type:      TaskUpdate_ASSIGNED,
						Time:      tutils.TimestampProto(t1),
					}
					r.Notify(ctx, s, taskUpdate)
					Convey("when AssignTasks is called again for the same worker", func() {
						as = r.AssignTasks(ctx, s, t2, &IdleWorker{ID: wid})
						Convey("then it is no longer given the task.", func() {
							So(as, ShouldBeEmpty)
						})
					})

				})

			})

		})
	})

}

// TestQueuedAssignment tests that a scheduler assignment is queued until
// the relevant worker calls AssignTasks.
func TestQueuedAssignment(t *testing.T) {
	ctx := context.Background()
	Convey("Given an empty scheduler and reconciler state", t, func() {
		t0 := time.Unix(0, 0)
		r := New()
		s := scheduler.New(t0)
		Convey("given a worker with a label is idle", func() {
			wid := "Worker1"
			labels := []string{"Label1"}
			r.AssignTasks(ctx, s, t0, &IdleWorker{wid, labels})
			Convey("given a request is enqueued with that label", func() {
				rid := "Request1"
				taskUpdate := &TaskUpdate{
					EnqueueTime:         tutils.TimestampProto(t0),
					Time:                tutils.TimestampProto(t0),
					ProvisionableLabels: labels,
					RequestId:           rid,
					Type:                TaskUpdate_NEW,
				}
				r.Notify(ctx, s, taskUpdate)
				Convey("when a different worker without that label calls AssignTasks", func() {
					wid2 := "Worker2"
					t1 := time.Unix(1, 0)
					as := r.AssignTasks(ctx, s, t1, &IdleWorker{wid2, []string{}})
					Convey("then it is given no task.", func() {
						So(as, ShouldBeEmpty)
					})
					Convey("when the labeled worker calls AssignTasks", func() {
						as = r.AssignTasks(ctx, s, t1, &IdleWorker{wid, labels})
						Convey("it is given the task.", func() {
							So(as, ShouldHaveLength, 1)
							So(as[0].RequestID, ShouldEqual, rid)
							So(as[0].WorkerID, ShouldEqual, wid)
						})
					})
				})
			})
		})

	})
}

func TestPreemption(t *testing.T) {
	ctx := context.Background()
	Convey("Given an empty scheduler and reconciler state", t, func() {
		t0 := time.Unix(0, 0)
		r := New()
		s := scheduler.New(t0)

		Convey("given a task and an idle worker, and that AssignTasks has been called and the worker is running that task", func() {
			oldRequest := "Request1"
			taskUpdate := &TaskUpdate{
				EnqueueTime: tutils.TimestampProto(t0),
				Time:        tutils.TimestampProto(t0),
				RequestId:   oldRequest,
				Type:        TaskUpdate_NEW,
			}
			r.Notify(ctx, s, taskUpdate)

			wid := "Worker1"
			r.AssignTasks(ctx, s, t0, &IdleWorker{ID: wid})

			// Note: This is more of a test of the scheduler's behavior than the
			// reconciler, but it is a precondition for the rest of the test cases.
			So(s.IsAssigned(oldRequest, wid), ShouldBeTrue)

			Convey("given a new request with higher priority", func() {
				aid := "Account1"
				s.AddAccount(ctx, aid, account.NewConfig(0, 0, vector.New()), vector.New(1))
				t1 := time.Unix(1, 0)
				newRequest := "Request2"
				taskUpdate := &TaskUpdate{
					AccountId:   aid,
					EnqueueTime: tutils.TimestampProto(t1),
					Time:        tutils.TimestampProto(t1),
					RequestId:   newRequest,
					Type:        TaskUpdate_NEW,
				}
				r.Notify(ctx, s, taskUpdate)

				Convey("when AssignTasks is called with no idle workers and the scheduler preempts the old request with the new one", func() {
					r.AssignTasks(ctx, s, t1)

					// Note: This is more of a test of the scheduler's behavior than the
					// reconciler, but it is a precondition for the rest of the test cases.
					So(s.IsAssigned(newRequest, wid), ShouldBeTrue)

					Convey("when GetCancellations is called", func() {
						c := r.Cancellations(ctx)
						Convey("then it returns a cancellation for the old request on that worker.", func() {
							So(c, ShouldHaveLength, 1)
							So(c[0].RequestID, ShouldEqual, oldRequest)
							So(c[0].WorkerID, ShouldEqual, wid)
						})
					})

					Convey("when Notify is called to inform that the old request is cancelled", func() {
						t2 := time.Unix(2, 0)
						taskUpdate := &TaskUpdate{
							Time:      tutils.TimestampProto(t2),
							RequestId: oldRequest,
							Type:      TaskUpdate_INTERRUPTED,
						}
						r.Notify(ctx, s, taskUpdate)
						Convey("when GetCancellations is called", func() {
							c := r.Cancellations(ctx)
							Convey("then it returns nothing.", func() {
								So(c, ShouldBeEmpty)
							})
						})
					})

					Convey("when AssignTasks is called for the intended worker", func() {
						t2 := time.Unix(2, 0)
						as := r.AssignTasks(ctx, s, t2, &IdleWorker{wid, []string{}})
						Convey("then it returns the preempting request.", func() {
							So(as, ShouldHaveLength, 1)
							So(as[0].RequestID, ShouldEqual, newRequest)
							So(as[0].WorkerID, ShouldEqual, wid)
						})
					})

					Convey("when AssignTasks is called for a different worker", func() {
						t2 := time.Unix(2, 0)
						wid2 := "Worker2"
						as := r.AssignTasks(ctx, s, t2, &IdleWorker{wid2, []string{}})
						Convey("then it returns the preempted request.", func() {
							So(as, ShouldHaveLength, 1)
							So(as[0].RequestID, ShouldEqual, oldRequest)
							So(as[0].WorkerID, ShouldEqual, wid2)
						})
					})

					Convey("when AssignTasks is called for the intended worker and a different worker simultaneously", func() {
						t2 := time.Unix(2, 0)
						wid2 := "Worker2"
						as := r.AssignTasks(ctx, s, t2, &IdleWorker{wid, []string{}}, &IdleWorker{wid2, []string{}})
						Convey("then intended worker receives preempting request, other receives preempted request.", func() {
							So(as, ShouldHaveLength, 2)
							a1 := Assignment{RequestID: newRequest, WorkerID: wid}
							a2 := Assignment{RequestID: oldRequest, WorkerID: wid2}
							asm := make(map[string]Assignment)
							for _, a := range as {
								asm[a.WorkerID] = a
							}
							So(asm[a1.WorkerID], ShouldResemble, a1)
							So(asm[a2.WorkerID], ShouldResemble, a2)
						})
					})
				})
			})
		})
	})
}
