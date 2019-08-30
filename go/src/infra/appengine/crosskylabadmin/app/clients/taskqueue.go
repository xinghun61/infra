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

package clients

import (
	"fmt"
	"net/url"

	"go.chromium.org/gae/service/taskqueue"
	"go.chromium.org/luci/common/logging"
	"golang.org/x/net/context"
)

const repairBotsQueue = "repair-bots"
const resetBotsQueue = "reset-bots"
const repairLabstationQueue = "repair-labstations"

// PushRepairLabstations pushes duts to taskqueue repairLabstationQueue for
// upcoming repair jobs.
func PushRepairLabstations(ctx context.Context, dutNames []string) error {
	return pushDUTs(ctx, dutNames, repairLabstationQueue, labstationRepairTask)
}

// PushRepairDUTs pushes duts to taskqueue repairBotsQueue for upcoming repair
// jobs.
func PushRepairDUTs(ctx context.Context, dutNames []string) error {
	return pushDUTs(ctx, dutNames, repairBotsQueue, crosRepairTask)
}

// PushResetDUTs pushes duts to taskqueue resetBotsQueue for upcoming reset
// jobs.
func PushResetDUTs(ctx context.Context, dutNames []string) error {
	return pushDUTs(ctx, dutNames, resetBotsQueue, resetTask)
}

func crosRepairTask(dn string) *taskqueue.Task {
	values := url.Values{}
	values.Set("dutName", dn)
	return taskqueue.NewPOSTTask(fmt.Sprintf("/internal/task/cros_repair/%s", dn), values)
}

func labstationRepairTask(dn string) *taskqueue.Task {
	values := url.Values{}
	values.Set("dutName", dn)
	return taskqueue.NewPOSTTask(fmt.Sprintf("/internal/task/labstation_repair/%s", dn), values)
}

func resetTask(dn string) *taskqueue.Task {
	values := url.Values{}
	values.Set("dutName", dn)
	return taskqueue.NewPOSTTask(fmt.Sprintf("/internal/task/reset/%s", dn), values)
}

func pushDUTs(ctx context.Context, dutNames []string, queueName string, taskGenerator func(string) *taskqueue.Task) error {
	tasks := make([]*taskqueue.Task, 0, len(dutNames))
	for _, dn := range dutNames {
		tasks = append(tasks, taskGenerator(dn))
	}
	if err := taskqueue.Add(ctx, queueName, tasks...); err != nil {
		return err
	}
	logging.Infof(ctx, "enqueued %d tasks", len(tasks))
	return nil
}
