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

package worker

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/worker"
)

// Task contains the information required to create a Skylab swarming task.
type Task struct {
	// The Swarming command to execute.
	Cmd []string
	// Tags to append to the swarming task.
	Tags []string
	// Name to use for the swarming task.
	Name string
}

// AdminTaskForType returns the information required to create a Skylab task
// for an admin task type.
func AdminTaskForType(ctx context.Context, ttype fleet.TaskType) Task {
	cmd := worker.Command{
		TaskName: fmt.Sprintf("admin_%s", strings.ToLower(ttype.String())),
	}
	cmd.Config(wrapped(config.Get(ctx)))
	t := Task{
		Name: taskName[ttype],
		Cmd:  cmd.Args(),
	}
	if cmd.LogDogAnnotationURL != "" {
		t.Tags = []string{fmt.Sprintf("log_location:%s", cmd.LogDogAnnotationURL)}
	}
	return t
}

// DeployTaskWithActions returns the information required to create a Skylab
// task for `lucifer deploytask`.
//
// actions may be empty to run the default deploytask with no actions.
func DeployTaskWithActions(ctx context.Context, actions string) Task {
	cmd := worker.Command{
		TaskName:   "deploy",
		ForceFresh: true,
		Actions:    actions,
	}
	cmd.Config(wrapped(config.Get(ctx)))
	t := Task{
		Name: "deploy",
		Cmd:  cmd.Args(),
	}
	if cmd.LogDogAnnotationURL != "" {
		t.Tags = []string{fmt.Sprintf("log_location:%s", cmd.LogDogAnnotationURL)}
	}
	return t
}

const (
	luciProject = "chromeos"
)

type environment struct {
	*config.Config
}

func wrapped(c *config.Config) *environment {
	return &environment{c}
}

// LUCIProject implements worker.Environment interface.
func (e *environment) LUCIProject() string {
	return luciProject
}

// LogDogHost implements worker.Environment interface.
func (e *environment) LogDogHost() string {
	return e.Tasker.LogdogHost
}

// GenerateLogPrefix implements worker.Environment interface.
func (e *environment) GenerateLogPrefix() string {
	return uuid.New().String()
}

var taskName = map[fleet.TaskType]string{
	fleet.TaskType_Cleanup: "AdminCleanup",
	fleet.TaskType_Repair:  "AdminRepair",
	fleet.TaskType_Reset:   "AdminReset",
}
