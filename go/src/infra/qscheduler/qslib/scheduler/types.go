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
	"fmt"
	"time"

	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/tutils"

	"go.chromium.org/luci/common/data/stringset"
)

var unixZeroTime = time.Unix(0, 0).UTC()

// NewConfig creates an returns a new Config instance with all maps initialized.
func NewConfig() *protos.SchedulerConfig {
	return &protos.SchedulerConfig{
		AccountConfigs: map[string]*protos.AccountConfig{},
	}
}

// newState creates an returns a new State instance with all maps initialized.
func newState(t time.Time) *state {
	return &state{
		balances:             map[AccountID]Balance{},
		queuedRequests:       map[RequestID]*TaskRequest{},
		workers:              map[WorkerID]*Worker{},
		runningRequestsCache: map[RequestID]WorkerID{},
		lastUpdateTime:       t,
	}
}

func toLabels(IDs []uint64, m map[uint64]string) stringset.Set {
	s := make([]string, len(IDs))
	for i, id := range IDs {
		if label, ok := m[id]; ok {
			s[i] = label
		} else {
			panic(fmt.Sprintf("id %d does not exist in label map", id))
		}
	}
	return stringset.NewFromSlice(s...)
}

func newStateFromProto(sp *protos.SchedulerState) *state {
	s := &state{}
	s.lastUpdateTime = tutils.Timestamp(sp.LastUpdateTime)
	s.queuedRequests = make(map[RequestID]*TaskRequest, len(sp.QueuedRequests))
	for rid, req := range sp.QueuedRequests {
		s.queuedRequests[RequestID(rid)] = protoToTaskRequest(RequestID(rid), req, sp.LabelMap)
	}

	s.runningRequestsCache = make(map[RequestID]WorkerID, len(sp.Workers))
	s.workers = make(map[WorkerID]*Worker, len(sp.Workers))
	for wid, w := range sp.Workers {
		var tr *taskRun
		if w.RunningTask != nil {
			cost := Balance{}
			copy(cost[:], w.RunningTask.Cost)
			tr = &taskRun{
				cost:     cost,
				priority: Priority(w.RunningTask.Priority),
				request:  protoToTaskRequest(RequestID(w.RunningTask.RequestId), w.RunningTask.Request, sp.LabelMap),
			}
			s.runningRequestsCache[RequestID(w.RunningTask.RequestId)] = WorkerID(wid)
		}
		modifiedTime := s.lastUpdateTime
		if w.ModifiedTime != nil {
			modifiedTime = tutils.Timestamp(w.ModifiedTime)
		}
		s.workers[WorkerID(wid)] = &Worker{
			ID:            WorkerID(wid),
			confirmedTime: tutils.Timestamp(w.ConfirmedTime),
			modifiedTime:  modifiedTime,
			Labels:        toLabels(w.LabelIds, sp.LabelMap),
			runningTask:   tr,
		}
	}

	s.balances = make(map[AccountID]Balance, len(sp.Balances))
	for aid, bal := range sp.Balances {
		newBal := Balance{}
		copy(newBal[:], bal.Value)
		s.balances[AccountID(aid)] = newBal
	}

	return s
}

func protoToTaskRequest(rid RequestID, p *protos.TaskRequest, labelMap map[uint64]string) *TaskRequest {
	examinedTime := unixZeroTime
	if p.ExaminedTime != nil {
		examinedTime = tutils.Timestamp(p.ExaminedTime)
	}
	return &TaskRequest{
		ID:                  rid,
		AccountID:           AccountID(p.AccountId),
		confirmedTime:       tutils.Timestamp(p.ConfirmedTime),
		examinedTime:        examinedTime,
		EnqueueTime:         tutils.Timestamp(p.EnqueueTime),
		ProvisionableLabels: toLabels(p.ProvisionableLabelIds, labelMap),
		BaseLabels:          toLabels(p.BaseLabelIds, labelMap),
	}
}

// TODO(akeshet): Move mapBuilder to internal package.

// mapBuilder builds a uint64<->string map, with each unique string being
// given a unique integer key.
//
// This is intended for use when serializing a State into a StateProto.
// It is not needed or used when going from StateProto to State.
type mapBuilder struct {
	nextID uint64
	m      map[uint64]string
	inv    map[string]uint64
}

// newMapBuilder initializes a mapBuilder.
func newMapBuilder() *mapBuilder {
	return &mapBuilder{
		m:   make(map[uint64]string),
		inv: make(map[string]uint64),
	}
}

// For determines an ID for the given string and returns it.
func (mb *mapBuilder) For(s string) uint64 {
	if id, ok := mb.inv[s]; ok {
		return id
	}

	mb.inv[s] = mb.nextID
	mb.m[mb.nextID] = s
	mb.nextID++

	return mb.nextID - 1
}

// ForSet determines an ID slice for the given string set and returns it.
func (mb *mapBuilder) ForSet(set stringset.Set) []uint64 {
	s := make([]uint64, len(set))
	i := 0
	for l := range set {
		s[i] = mb.For(l)
		i++
	}
	return s
}

// Map returns the ID -> string map for this mapBuilder.
func (mb *mapBuilder) Map() map[uint64]string {
	return mb.m
}

func (s *state) toProto() *protos.SchedulerState {
	mb := newMapBuilder()

	balances := make(map[string]*protos.SchedulerState_Balance, len(s.balances))
	for aid, bal := range s.balances {
		bCopy := bal
		balances[string(aid)] = &protos.SchedulerState_Balance{Value: bCopy[:]}
	}

	queuedRequests := make(map[string]*protos.TaskRequest, len(s.queuedRequests))
	for rid, rq := range s.queuedRequests {
		queuedRequests[string(rid)] = requestProto(rq, mb)
	}

	workers := make(map[string]*protos.Worker, len(s.workers))
	for wid, w := range s.workers {
		var rt *protos.TaskRun
		if w.runningTask != nil {
			costCopy := w.runningTask.cost
			rt = &protos.TaskRun{
				Cost:      costCopy[:],
				Priority:  int32(w.runningTask.priority),
				Request:   requestProto(w.runningTask.request, mb),
				RequestId: string(w.runningTask.request.ID),
			}
		}
		workers[string(wid)] = &protos.Worker{
			ConfirmedTime: tutils.TimestampProto(w.confirmedTime),
			ModifiedTime:  tutils.TimestampProto(w.modifiedTime),
			RunningTask:   rt,
			LabelIds:      mb.ForSet(w.Labels),
		}
	}

	return &protos.SchedulerState{
		Balances:       balances,
		LastUpdateTime: tutils.TimestampProto(s.lastUpdateTime),
		QueuedRequests: queuedRequests,
		Workers:        workers,
		LabelMap:       mb.Map(),
	}
}

// Clone returns a deep copy of state, by doing a round-trip proto serialization.
func (s *state) Clone() *state {
	return newStateFromProto(s.toProto())
}
