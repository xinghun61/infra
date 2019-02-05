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

package scheduler

import (
	"time"

	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

// NewConfig creates an returns a new Config instance with all maps initialized.
func NewConfig() *Config {
	return &Config{
		AccountConfigs: map[string]*AccountConfig{},
	}
}

// newState creates an returns a new State instance with all maps initialized.
func newState(t time.Time) *state {
	return &state{
		balances:       map[AccountID]balance{},
		queuedRequests: map[RequestID]*TaskRequest{},
		workers:        map[WorkerID]*worker{},
		lastUpdateTime: t,
	}
}

func newStateFromProto(sp *StateProto) *state {
	s := &state{}
	s.lastUpdateTime = tutils.Timestamp(sp.LastUpdateTime)
	s.queuedRequests = make(map[RequestID]*TaskRequest, len(sp.QueuedRequests))
	for rid, req := range sp.QueuedRequests {
		s.queuedRequests[RequestID(rid)] = &TaskRequest{
			ID:                  RequestID(rid),
			AccountID:           AccountID(req.AccountId),
			confirmedTime:       tutils.Timestamp(req.ConfirmedTime),
			EnqueueTime:         tutils.Timestamp(req.EnqueueTime),
			ProvisionableLabels: stringset.NewFromSlice(req.ProvisionableLabels...),
			BaseLabels:          stringset.NewFromSlice(req.BaseLabels...),
		}
	}

	s.runningRequestsCache = make(map[RequestID]WorkerID, len(sp.Workers))
	s.workers = make(map[WorkerID]*worker, len(sp.Workers))
	for wid, w := range sp.Workers {
		var tr *taskRun
		if w.RunningTask != nil {
			cost := balance{}
			copy(cost[:], w.RunningTask.Cost)
			tr = &taskRun{
				cost:     cost,
				priority: Priority(w.RunningTask.Priority),
				request: &TaskRequest{
					ID:                  RequestID(w.RunningTask.RequestId),
					AccountID:           AccountID(w.RunningTask.Request.AccountId),
					confirmedTime:       tutils.Timestamp(w.RunningTask.Request.ConfirmedTime),
					EnqueueTime:         tutils.Timestamp(w.RunningTask.Request.EnqueueTime),
					ProvisionableLabels: stringset.NewFromSlice(w.RunningTask.Request.ProvisionableLabels...),
					BaseLabels:          stringset.NewFromSlice(w.RunningTask.Request.BaseLabels...),
				},
			}
			s.runningRequestsCache[RequestID(w.RunningTask.RequestId)] = WorkerID(wid)
		}
		s.workers[WorkerID(wid)] = &worker{
			ID:            WorkerID(wid),
			confirmedTime: tutils.Timestamp(w.ConfirmedTime),
			labels:        stringset.NewFromSlice(w.Labels...),
			runningTask:   tr,
		}
	}

	s.balances = make(map[AccountID]balance, len(sp.Balances))
	for aid, bal := range sp.Balances {
		newBal := balance{}
		copy(newBal[:], bal.Value)
		s.balances[AccountID(aid)] = newBal
	}

	return s
}

func (s *state) toProto() *StateProto {
	balances := make(map[string]*StateProto_Balance, len(s.balances))
	for aid, bal := range s.balances {
		bCopy := bal
		balances[string(aid)] = &StateProto_Balance{Value: bCopy[:]}
	}

	queuedRequests := make(map[string]*TaskRequestProto, len(s.queuedRequests))
	for rid, rq := range s.queuedRequests {
		queuedRequests[string(rid)] = requestProto(rq)
	}

	workers := make(map[string]*Worker, len(s.workers))
	for wid, w := range s.workers {
		var rt *TaskRun
		if w.runningTask != nil {
			costCopy := w.runningTask.cost
			rt = &TaskRun{
				Cost:      costCopy[:],
				Priority:  int32(w.runningTask.priority),
				Request:   requestProto(w.runningTask.request),
				RequestId: string(w.runningTask.request.ID),
			}
		}
		workers[string(wid)] = &Worker{
			ConfirmedTime: tutils.TimestampProto(w.confirmedTime),
			Labels:        w.labels.ToSlice(),
			RunningTask:   rt,
		}
	}

	return &StateProto{
		Balances:       balances,
		LastUpdateTime: tutils.TimestampProto(s.lastUpdateTime),
		QueuedRequests: queuedRequests,
		Workers:        workers,
	}
}

// Clone returns a deep copy of state, by doing a round-trip proto serialization.
func (s *state) Clone() *state {
	return newStateFromProto(s.toProto())
}
