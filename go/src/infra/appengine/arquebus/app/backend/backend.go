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

// Package backend implements the core logic of Arquebus service.
package backend

import (
	"context"
	"net/http"
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
	"infra/appengine/arquebus/app/util"
	"infra/monorailv2/api/api_proto"
)

var (
	// maxIssueUpdatesExecutionTime is the maximum duration that a single Task
	// run can spend for issue searches and updates.
	maxIssueUpdatesExecutionTime = time.Second * 40

	// nRetriesForSavingTaskEntity is the maximum number of trasnsactions that
	// should be attempted to save Task entity in endTaskRun().
	//
	// After searchAndUpdateIssues(), the status of the Task entity is set
	// with one of Failed, Succeeded, and Aborted. However, if it fails to
	// save the Task entity in datastore, Arquebus returns nil to TaskQueue
	// to prevent the TQ work from being retried and performing another
	// searchAndUpdateIssues().
	nRetriesForSavingTaskEntity = 8
)

var ctxKeyMonorailClient = "monorail client"

func setMonorailClient(c context.Context, mc monorail.IssuesClient) context.Context {
	return context.WithValue(c, &ctxKeyMonorailClient, mc)
}

func getMonorailClient(c context.Context) monorail.IssuesClient {
	return c.Value(&ctxKeyMonorailClient).(monorail.IssuesClient)
}

func createMonorailClient(c context.Context) (monorail.IssuesClient, error) {
	transport, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	return monorail.NewIssuesPRPCClient(
		&prpc.Client{
			C:    &http.Client{Transport: transport},
			Host: config.Get(c).MonorailHostname,
		},
	), nil
}

// InstallHandlers installs TaskQueue handlers into a given task queue.
func InstallHandlers(r *router.Router, dispatcher *tq.Dispatcher, m router.MiddlewareChain) {
	registerTaskHandlers(dispatcher)

	// install the dispatcher and monorail client into the context so that
	// they can be accessed via the context and overwritten in unit tests.
	m = m.Extend(func(rc *router.Context, next router.Handler) {
		rc.Context = util.SetDispatcher(rc.Context, dispatcher)

		mc, err := createMonorailClient(rc.Context)
		if err != nil {
			util.ErrStatus(
				rc, http.StatusInternalServerError,
				"failed to create an RPC channel for Monorail: %s", err,
			)
			return
		}
		rc.Context = setMonorailClient(rc.Context, mc)
		next(rc)
	})
	dispatcher.InstallRoutes(r, m)
}

func registerTaskHandlers(dispatcher *tq.Dispatcher) {
	dispatcher.RegisterTask(
		&ScheduleAssignerTask{}, scheduleAssignerTaskHandler,
		"schedule-assigners", nil,
	)
	dispatcher.RegisterTask(
		&RunAssignerTask{}, runAssignerTaskHandler,
		"run-assigners", nil,
	)
}

// GetAllAssigners returns all assigners.
func GetAllAssigners(c context.Context) ([]*model.Assigner, error) {
	return model.GetAllAssigners(c)
}

// GetAssigner returns the Assigner matching with a given ID.
func GetAssigner(c context.Context, aid string) (*model.Assigner, error) {
	return model.GetAssigner(c, aid)
}

// UpdateAssigners updates all the Assigner entities, based on the configs,
// and remove the assigners of which configs no longer exist.
func UpdateAssigners(c context.Context, cfgs []*config.Assigner, rev string) error {
	// TODO(crbug/849469): validate the input configs. It's possible that
	// an existing, valid config becomes invalid due to application code
	// changes.
	return model.UpdateAssigners(c, cfgs, rev)
}

// GetAssignerWithTasks returns up to |limit| of Task entities for
// the Assigner in ExpectedStart desc order.
//
// If includeNoopSuccess is true, the return includes the Task entities
// that were completed successfully without issue updates.
func GetAssignerWithTasks(c context.Context, assignerID string, limit int32, includeNoopSuccess bool) (assigner *model.Assigner, tasks []*model.Task, err error) {
	if assigner, err = model.GetAssigner(c, assignerID); err == nil {
		tasks, err = model.GetTasks(c, assigner, limit, includeNoopSuccess)
	}
	return
}

// GetTask returns the task entity matching with the assigner and task IDs.
func GetTask(c context.Context, assignerID string, taskID int64) (*model.Assigner, *model.Task, error) {
	return model.GetTask(c, assignerID, taskID)
}

//////////////////////////////////////////////////////////////////////////////
//
// TaskQueue handlers

// scheduleAssignerTaskHandler ensures that a given assigner has at least
// one task scheduled.
func scheduleAssignerTaskHandler(c context.Context, tqTask proto.Message) error {
	msg := tqTask.(*ScheduleAssignerTask)
	return datastore.RunInTransaction(c, func(c context.Context) error {
		tasks, err := model.EnsureScheduledTasks(c, msg.AssignerId)
		if err != nil {
			return err
		}
		return scheduleRuns(c, msg.AssignerId, tasks)
	}, &datastore.TransactionOptions{})
}

func scheduleRuns(c context.Context, assignerID string, tasks []*model.Task) error {
	tqTasks := make([]*tq.Task, len(tasks))
	for i, task := range tasks {
		tqTasks[i] = &tq.Task{
			Payload: &RunAssignerTask{
				AssignerId: assignerID,
				TaskId:     task.ID,
			},
			ETA: task.ExpectedStart,
		}
	}
	return util.GetDispatcher(c).AddTask(c, tqTasks...)
}

// startTaskRun updates the task status, based on the current status of
// the assigner and task.
func startTaskRun(c context.Context, assignerID string, taskID int64) (assigner *model.Assigner, task *model.Task, err error) {
	err = datastore.RunInTransaction(c, func(c context.Context) error {
		assigner, task, err = model.GetTask(c, assignerID, taskID)
		if err != nil {
			return err
		}
		if task.Status != model.TaskStatus_Scheduled {
			logging.Warningf(c, ""+
				`the status is not "scheduled.", but "%q". It's likely `+
				`that this Task run has been already processed by `+
				`another worker`,
				task.Status,
			)
			// return nil for assigner and task so that this TQ work will end
			// immediately without processing the Assigner Task.
			assigner = nil
			task = nil
			return nil
		}

		now := clock.Now(c).UTC()
		task.Started = now
		nextSch := task.ExpectedStart.Add(assigner.Interval)

		// check for drained assigner and stale tasks,
		switch {
		case assigner.IsDrained:
			task.Status = model.TaskStatus_Cancelled
			task.WriteLog(c, "the assigner has been drained; cancelling")
			task.Ended = now

		case nextSch.Before(now.Add(maxIssueUpdatesExecutionTime)):
			// It's either the task is stale or the remaining time is not long
			// enough to have the maximum issue update execution time.
			task.Status = model.TaskStatus_Cancelled
			task.WriteLog(c, ""+
				"stale task or the remaining time before the next schedule "+
				"is too short; there should be at least %s left; cancelling",
				maxIssueUpdatesExecutionTime)
			task.Ended = now

		default:
			task.Status = model.TaskStatus_Running
		}

		if err := datastore.Put(c, task); err != nil {
			return err
		}
		return nil
	}, &datastore.TransactionOptions{})
	return
}

// endTaskRun updates the task status, based on the current status of
// the assigner and task.
func endTaskRun(c context.Context, task *model.Task, nIssuesUpdated int, issueUpdateError error) error {
	switch {
	// As long as at least one issue has been updated, then it should be
	// marked as succeeded, even if it stopped after an error or timeout.
	case nIssuesUpdated > 0:
		task.Status = model.TaskStatus_Succeeded
	case issueUpdateError == context.DeadlineExceeded:
		task.Status = model.TaskStatus_Aborted
	case issueUpdateError != nil:
		task.Status = model.TaskStatus_Failed
	default:
		// TODO(crbug/849469): replace Task.WasNoopSuccess with
		// Task.nIssuesUpdated.
		task.WasNoopSuccess = true
		task.Status = model.TaskStatus_Succeeded
	}
	task.Ended = clock.Now(c).UTC()

	return datastore.RunInTransaction(c, func(c context.Context) error {
		return datastore.Put(c, task)
	}, &datastore.TransactionOptions{Attempts: nRetriesForSavingTaskEntity})
}

// runAssignerTaskHandler runs an Assigner task, based on the Task entity.
func runAssignerTaskHandler(c context.Context, tqTask proto.Message) error {
	msg := tqTask.(*RunAssignerTask)

	assigner, task, err := startTaskRun(c, msg.AssignerId, msg.TaskId)
	if err != nil {
		// if it fails to update the Task entity with a new status, then
		// returns an error to trigger retries.
		return err
	} else if task == nil || task.Status != model.TaskStatus_Running {
		return nil
	}

	// At this moment, the assigner might have been drained. However, this
	// task run should continue, as draining an assigner doesn't cancel
	// a running task.
	//
	// If errors occur within searchAndUpdateIssues(), that means either
	// Monorail is flaky or unavailable. searchAndUpdateIssues() just marks
	// the Task as failed, and the Task run ends here without retries.
	timedCtx, cancel := context.WithTimeout(c, maxIssueUpdatesExecutionTime)
	defer cancel()
	nIssuesUpdated, issueUpdateErr := searchAndUpdateIssues(
		timedCtx, assigner, task,
	)
	// if the error was due to the context timeout, override issueUpdateErr
	// with it so that endTaskRun() can recognize the timeout error.
	if err != nil && timedCtx.Err() == context.DeadlineExceeded {
		issueUpdateErr = context.DeadlineExceeded
	}

	if err := endTaskRun(c, task, nIssuesUpdated, issueUpdateErr); err != nil {
		// If datastore.Put() fails, ignore the error. Returning the error
		// will cause the TQ task retried and searchAndUpdateIssues() will
		// be performed again.
		issueUpdateResult := "successful searchAndUpdateIssues()."
		if issueUpdateErr != nil {
			issueUpdateResult = "un" + issueUpdateResult
		}
		logging.Errorf(
			c, "Failed to update Task entity after %s; %s",
			issueUpdateResult, err,
		)
	}
	return nil
}
