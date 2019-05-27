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

package model

import (
	"context"
	"fmt"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/clock"
)

type logEntry struct {
	Timestamp time.Time
	Message   string
}

const (
	taskKind = "Task"
)

// Task keeps track of a single Assigner invocation before, during, and after
// its execution.
type Task struct {
	_kind  string                `gae:"$kind,Task"`
	_extra datastore.PropertyMap `gae:"-,extra"`

	ID          int64          `gae:"$id"`
	AssignerKey *datastore.Key `gae:"$parent"`

	// ExpectedStart is the time that the task has been scheduled to run for.
	ExpectedStart time.Time
	// Started is the time the task started.
	//
	// The value has no meaning if the task has not run yet.
	Started time.Time `gae:",noindex"`
	// Ended is the time the current task was completed.
	//
	// The value has no meaning until the task has been succeeded or failed.
	Ended time.Time `gae:",noindex"`

	Status TaskStatus
	// WasNoopSuccess is true if the task successfully completed without
	// any issues updated. False, otherwise.
	WasNoopSuccess bool

	// Logs are an optional list of log entries, each is printed in a separate
	// line in UI.
	Logs []logEntry `gae:",noindex"`
}

// WriteLog appends a new line with the message into the Task entity.
func (task *Task) WriteLog(c context.Context, format string, args ...interface{}) {
	task.Logs = append(task.Logs, logEntry{
		Timestamp: clock.Now(c).UTC(),
		Message:   fmt.Sprintf(format, args...),
	})
}

// GetTask returns the Task entity matching with the Assigner and Task IDs.
func GetTask(c context.Context, assignerID string, taskID int64) (*Assigner, *Task, error) {
	assigner, err := GetAssigner(c, assignerID)
	if err != nil {
		return nil, nil, err
	}
	task := &Task{AssignerKey: GenAssignerKey(c, assigner), ID: taskID}
	if err := datastore.Get(c, task); err != nil {
		return nil, nil, err
	}

	return assigner, task, nil
}

// GetTasks returns up to |limit| of Task entities in ExpectedStart desc order.
//
// If includeNoopSuccess is true, the return includes the Task entities
// that were completed successfully without issue updates.
//
// TODO(crbug/849469): add pagination
func GetTasks(c context.Context, assigner *Assigner, limit int32, includeNoopSuccess bool) ([]*Task, error) {
	var tasks []*Task
	q := datastore.NewQuery(taskKind).Ancestor(GenAssignerKey(c, assigner))
	if includeNoopSuccess == false {
		q = q.Eq("WasNoopSuccess", false)
	}
	q = q.Order("-ExpectedStart").Limit(limit)
	if err := datastore.GetAll(c, q, &tasks); err != nil {
		return nil, err
	}
	return tasks, nil
}
