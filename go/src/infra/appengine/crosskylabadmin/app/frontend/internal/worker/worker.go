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
)

const (
	// infraToolsDir is the well known path to infra tools deployed on the drone.
	infraToolsDir = "/opt/infra-tools"
	// skylabSwarmingWorkerPath is the path to the binary on the drone that is
	// the entry point of all tasks.
	skylabSwarmingWorkerPath = infraToolsDir + "/skylab_swarming_worker"
)

// AdminTask contains the information required to create a Swarming task for an
// admin task.
type AdminTask struct {
	// The Swarming command to execute.
	Cmd []string

	// Tags to append to the swarming task.
	Tags []string

	// Name to use for the swarming task.
	Name string
}

// AdminTaskForType returns the information required to create a Skylab task
// for an admin task type.
func AdminTaskForType(ctx context.Context, ttype fleet.TaskType) AdminTask {
	at := AdminTask{
		Name: taskName[ttype],
	}
	cfg := config.Get(ctx)
	logdogURL := generateLogDogURL(cfg)
	if logdogURL != "" {
		at.Tags = []string{fmt.Sprintf("log_location:%s", logdogURL)}
	}
	at.Cmd = adminTaskCmd(ctx, ttype, logdogURL)
	return at
}

func adminTaskCmd(ctx context.Context, ttype fleet.TaskType, logdogURL string) []string {
	s := []string{
		skylabSwarmingWorkerPath,
		"-task-name", fmt.Sprintf("admin_%s", strings.ToLower(ttype.String())),
	}
	if logdogURL != "" {
		s = append(s, "-logdog-annotation-url", logdogURL)
	}
	return s
}

var taskName = map[fleet.TaskType]string{
	fleet.TaskType_Cleanup: "AdminCleanup",
	fleet.TaskType_Repair:  "AdminRepair",
	fleet.TaskType_Reset:   "AdminReset",
}

// generateLogDogURL generates a LogDog annotation URL for the LogDog server
// corresponding to the configured Swarming server.
//
// If the LogDog server can't be determined, an empty string is returned.
func generateLogDogURL(cfg *config.Config) string {
	if cfg.Tasker.LogdogHost != "" {
		return logdogAnnotationURL(cfg.Tasker.LogdogHost, uuid.New().String())
	}
	return ""
}

// logdogAnnotationURL generates a LogDog annotation URL for the LogDog server.
func logdogAnnotationURL(server, id string) string {
	return fmt.Sprintf("logdog://%s/chromeos/skylab/%s/+/annotations",
		server, id)
}
