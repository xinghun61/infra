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

package frontend

import (
	"context"
	"sort"
	"time"

	"go.chromium.org/luci/grpc/grpcutil"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"

	"infra/qscheduler/qslib/protos"
)

// QSchedulerViewServerImpl implements QSchedulerViewServer.
type QSchedulerViewServerImpl struct{}

// InspectPool implements QSchedulerAdminServer.
func (s *QSchedulerViewServerImpl) InspectPool(ctx context.Context, r *qscheduler.InspectPoolRequest) (resp *qscheduler.InspectPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	sp, err := store.Get(ctx)
	if err != nil {
		return nil, err
	}

	t0 := time.Now()
	workers := sp.Scheduler.GetWorkers()
	running := make([]*qscheduler.InspectPoolResponse_RunningTask, 0, len(workers))
	idle := make([]*qscheduler.InspectPoolResponse_IdleBot, 0, len(workers))
	for wid, w := range workers {
		age := int32(t0.Sub(w.ConfirmedTime()).Seconds())
		if w.IsIdle() {
			idle = append(idle, &qscheduler.InspectPoolResponse_IdleBot{
				Id:         string(wid),
				Dimensions: w.Labels.ToSlice(),
				AgeSeconds: age,
			})
		} else {
			request := w.RunningRequest()
			running = append(running, &qscheduler.InspectPoolResponse_RunningTask{
				BotId:      string(wid),
				Id:         string(request.ID),
				Priority:   int32(w.RunningPriority()),
				AccountId:  string(request.AccountID),
				AgeSeconds: age,
			})
		}
	}

	waitingRequests := sp.Scheduler.GetWaitingRequests()
	waiting := make([]*qscheduler.InspectPoolResponse_WaitingTask, 0, len(waitingRequests))
	for rid, r := range waitingRequests {
		waiting = append(waiting, &qscheduler.InspectPoolResponse_WaitingTask{
			Id:         string(rid),
			AccountId:  string(r.AccountID),
			AgeSeconds: int32(t0.Sub(r.ConfirmedTime()).Seconds()),
		})
	}

	balances := sp.Scheduler.GetBalances()
	responseBalance := make(map[string]*protos.SchedulerState_Balance)
	for aid, b := range balances {
		bCopy := b
		responseBalance[string(aid)] = &protos.SchedulerState_Balance{
			Value: bCopy[:],
		}
	}

	// Sort items by age, to make it easy and convenient for users
	// to find oldest.
	sort.Slice(idle, func(i, j int) bool {
		return older(idle[i], idle[j])
	})
	sort.Slice(running, func(i, j int) bool {
		return older(running[i], running[j])
	})
	sort.Slice(waiting, func(i, j int) bool {
		return older(waiting[i], waiting[j])
	})

	resp = &qscheduler.InspectPoolResponse{
		NumWaitingTasks:   int32(len(waiting)),
		NumIdleBots:       int32(len(idle)),
		NumRunningTasks:   int32(len(running)),
		RunningTasks:      running,
		WaitingTasks:      waiting,
		IdleBots:          idle,
		AccountBalances:   responseBalance,
		AccountConfigs:    sp.Scheduler.Config().ToProto().AccountConfigs,
		DisablePreemption: sp.Scheduler.Config().DisablePreemption,
	}

	return resp, nil
}

type getAgeSecondsAble interface {
	GetAgeSeconds() int32
}

// Returns true if a is older than b.
func older(a getAgeSecondsAble, b getAgeSecondsAble) bool {
	return a.GetAgeSeconds() > b.GetAgeSeconds()
}
