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

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/appengine/tq"
	"go.chromium.org/luci/server/router"

	"infra/appengine/arquebus/app/backend/model"
	"infra/appengine/arquebus/app/config"
)

var (
	dispatcher = tq.Dispatcher{BaseURL: "/internal/tq/"}
)

// Dispatcher returns the dispatcher instance to be used by all other
// modules to interact with the backend module.
func Dispatcher() *tq.Dispatcher {
	return &dispatcher
}

// InstallHandlers installs TaskQueue handlers into a given task queue.
func InstallHandlers(r *router.Router, m router.MiddlewareChain) {
	dispatcher.RegisterTask(
		&ScheduleAssignerTask{}, scheduleAssignerTaskHandler,
		"schedule-assigners", nil,
	)
	dispatcher.RegisterTask(
		&RunAssignerTask{}, runAssignerTaskHandler,
		"run-assigners", nil,
	)
	dispatcher.InstallRoutes(r, m)
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
	err = datastore.RunInTransaction(c, func(c context.Context) error {
		if assigner, err = model.GetAssigner(c, assignerID); err != nil {
			return err
		}
		tasks, err = model.GetTasks(c, assigner, limit, includeNoopSuccess)
		return err
	}, &datastore.TransactionOptions{})
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

func runAssignerTaskHandler(c context.Context, tqTask proto.Message) error {
	// TODO(crbug/849469): implement this
	return nil
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
	return Dispatcher().AddTask(c, tqTasks...)
}
