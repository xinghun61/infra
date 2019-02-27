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
	"go.chromium.org/gae/service/info"

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

// AdminTaskCmd returns a slice of strings for a skylab_swarming_worker admin
// task command.
//
// logdogURL, if non-empty, is used as the LogDog annotation URL.
func AdminTaskCmd(ctx context.Context, ttype fleet.TaskType, logdogURL string) []string {
	s := []string{
		skylabSwarmingWorkerPath,
		"-task-name", fmt.Sprintf("admin_%s", strings.ToLower(ttype.String())),
	}
	s = append(s, "-admin-service", fmt.Sprintf("%s.appspot.com", info.AppID(ctx)))
	if logdogURL != "" {
		s = append(s, "-logdog-annotation-url", logdogURL)
	}
	return s
}

// GenerateLogDogURL generates a LogDog annotation URL for the LogDog server
// corresponding to the configured Swarming server.
//
// If the LogDog server can't be determined, an empty string is returned.
func GenerateLogDogURL(cfg *config.Config) string {
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
