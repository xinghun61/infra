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

package types

import (
	"context"
	"time"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

// Operation is the type for functions that examine and mutate a state.
type Operation func(ctx context.Context, state *QScheduler, events scheduler.EventSink)

// QScheduler encapsulates the state of a scheduler.
type QScheduler struct {
	// TODO: Drop this entry from the struct.
	SchedulerID string
	Scheduler   *scheduler.Scheduler
	Reconciler  *reconciler.State
}

// NewQScheduler returns a new QSchedulerState instance.
func NewQScheduler(id string, t time.Time, c *scheduler.Config) *QScheduler {
	return &QScheduler{
		SchedulerID: id,
		Scheduler:   scheduler.NewWithConfig(t, c),
		Reconciler:  reconciler.New(),
	}
}
