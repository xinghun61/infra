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

// Package diagnosis implements DUT state diagnosis.
package diagnosis

import (
	"context"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
)

const diagnosisTaskLimit = 200

// BotTaskLister is the interface used by Diagnose to list bot tasks.
type BotTaskLister interface {
	ListBotTasks(string) clients.BotTasksCursor
}

// Diagnose returns information about a bot based on its tasks.
func Diagnose(ctx context.Context, sc BotTaskLister, botID string, s fleet.DutState) ([]*fleet.Task, error) {
	c := sc.ListBotTasks(botID)
	p := clients.Pager{Remaining: diagnosisTaskLimit}
	b := newDiagnosisBuilder(s)
	for {
		chunk := p.Next()
		if chunk == 0 {
			break
		}
		ts, err := c.Next(ctx, int64(chunk))
		if err != nil {
			return b.tasks, errors.Reason("failed to list tasks for bot %s", botID).InternalReason(err.Error()).Err()
		}
		if len(ts) == 0 {
			break
		}
		if done := b.consume(ts); done {
			break
		}
		p.Record(len(ts))
	}
	return b.tasks, nil
}

// diagnosisBuilder builds a slice of diagnosis tasks.
type diagnosisBuilder struct {
	annotator   stateAnnotator
	tasks       []*fleet.Task
	foundRepair bool
	foundChange bool
	done        bool
}

func newDiagnosisBuilder(s fleet.DutState) *diagnosisBuilder {
	return &diagnosisBuilder{
		annotator: stateAnnotator{
			prev: s,
		},
	}
}

// consume consumes tasks to build a diagnosis.
// This method returns true if no more tasks are needed.
func (b *diagnosisBuilder) consume(s []*swarming.SwarmingRpcsTaskResult) bool {
	if b.done {
		return true
	}
	for _, t := range s {
		a := b.annotator.annotate(t)
		// Make it convenient to track that each task is only
		// added once.
		added := false
		addTask := func() {
			if added {
				return
			}
			// TODO(ayatane): Maybe log conversion errors?
			ft, _ := convertTask(t, a)
			b.tasks = append(b.tasks, ft)
			added = true
		}
		// Add the newest repair task to the diagnosis.
		if !b.foundRepair && isRepair(t) {
			addTask()
			b.foundRepair = true
			continue
		}
		// We want to find the newest sequence of tasks that
		// changed the DUT state.
		if a.before == a.after {
			if !b.foundChange {
				continue
			}
			b.done = true
			return true
		}
		b.foundChange = true
		addTask()
	}
	return false
}

func isRepair(t *swarming.SwarmingRpcsTaskResult) bool {
	// TODO(ayatane): There's probably a better way to do this
	// than relying on an exact name match.
	return t.Name == "AdminRepair"
}

// convertTask converts the Swarming task result to the task returned
// by the tracker API.  A partial usable task is returned even if an
// error prevents conversion of some fields.
func convertTask(t *swarming.SwarmingRpcsTaskResult, a stateAnnot) (*fleet.Task, error) {
	tm, err := time.Parse(clients.SwarmingTimeLayout, t.StartedTs)
	var ts *timestamp.Timestamp
	if err == nil {
		ts, err = ptypes.TimestampProto(tm)
	}
	return &fleet.Task{
		Id:          t.TaskId,
		Name:        t.Name,
		StateBefore: a.before,
		StateAfter:  a.after,
		StartedTs:   ts,
	}, errors.Annotate(err, "failed to convert task %s", t.TaskId).Err()
}

// stateAnnot contains annotations for the DUT state before and
// after a task.
type stateAnnot struct {
	before fleet.DutState
	after  fleet.DutState
}

// stateAnnotator annotates a sequence of tasks with the DUT state
// before and after.  (Swarming only provides the dimensions at the
// start of a task.)
type stateAnnotator struct {
	prev fleet.DutState
}

// annotate annotates a task with the DUT state before and after.
// This method must be called exactly once for each task in
// sequence.
func (a *stateAnnotator) annotate(t *swarming.SwarmingRpcsTaskResult) stateAnnot {
	new := clients.GetStateDimension(t.BotDimensions)
	r := stateAnnot{
		before: new,
		after:  a.prev,
	}
	a.prev = new
	return r
}
