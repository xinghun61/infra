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

package diagnosis_test

import (
	"context"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/kylelemons/godebug/pretty"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/frontend/internal/diagnosis"
)

func TestDiagnose(t *testing.T) {
	t.Parallel()
	t.Run("repair fail", func(t *testing.T) {
		t.Parallel()
		sc := &swarmingClientTasksStub{
			tasks: []*swarming.SwarmingRpcsTaskResult{
				makeTask("AdminRepair", "repair_failed", 16),
				makeTask("AdminRepair", "repair_failed", 15),
				makeTask("AdminRepair", "repair_failed", 14),
				makeTask("AdminRepair", "needs_repair", 13),
				makeTask("some_test", "ready", 12),
				makeTask("some_test", "ready", 11),
				makeTask("some_test", "ready", 10),
			},
		}
		got, err := diagnosis.Diagnose(context.Background(), sc, "some bot", fleet.DutState_RepairFailed)
		if err != nil {
			t.Fatalf("Diagnose returned an error: %#v", err)
		}
		want := []*fleet.Task{
			{
				Name:        "AdminRepair",
				StateAfter:  fleet.DutState_RepairFailed,
				StateBefore: fleet.DutState_RepairFailed,
				StartedTs:   makeTs(16),
			},
			{
				Name:        "AdminRepair",
				StateAfter:  fleet.DutState_RepairFailed,
				StateBefore: fleet.DutState_NeedsRepair,
				StartedTs:   makeTs(13),
			},
			{
				Name:        "some_test",
				StateAfter:  fleet.DutState_NeedsRepair,
				StateBefore: fleet.DutState_Ready,
				StartedTs:   makeTs(12),
			},
		}
		if diff := pretty.Compare(want, got); diff != "" {
			t.Errorf("tasks differ -want +got, %s", diff)
		}
	})
}

func makeTs(seq int) *timestamp.Timestamp {
	return &timestamp.Timestamp{Seconds: int64(seq)}
}

func makeTask(name string, state string, seq int) *swarming.SwarmingRpcsTaskResult {
	return &swarming.SwarmingRpcsTaskResult{
		Name: name,
		BotDimensions: []*swarming.SwarmingRpcsStringListPair{
			{
				Key:   "dut_state",
				Value: []string{state},
			},
		},
		StartedTs: time.Unix(int64(seq), 0).UTC().Format(clients.SwarmingTimeLayout),
	}
}

// swarmingClientTasksStub provides canned responses to ListBotTasks.
type swarmingClientTasksStub struct {
	tasks []*swarming.SwarmingRpcsTaskResult
}

func (c *swarmingClientTasksStub) ListBotTasks(id string) clients.BotTasksCursor {
	return &simpleCursor{
		tasks: c.tasks,
	}
}

var _ clients.BotTasksCursor = &simpleCursor{}

// simpleCursor cursors through a list of task results.
type simpleCursor struct {
	tasks []*swarming.SwarmingRpcsTaskResult
	i     int
}

func (c *simpleCursor) Next(ctx context.Context, n int64) ([]*swarming.SwarmingRpcsTaskResult, error) {
	start := c.i
	if end := c.i + int(n); end < len(c.tasks) {
		c.i = end
	} else {
		c.i = len(c.tasks)
	}
	return c.tasks[start:c.i], nil
}
