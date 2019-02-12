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

package frontend

import (
	"context"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/grpc/grpcutil"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/state"
	"infra/appengine/qscheduler-swarming/app/state/types"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// QSchedulerAdminServerImpl implements QSchedulerAdminServer.
type QSchedulerAdminServerImpl struct{}

// QSchedulerViewServerImpl implements QSchedulerViewServer.
type QSchedulerViewServerImpl struct{}

// CreateSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateSchedulerPool(ctx context.Context, r *qscheduler.CreateSchedulerPoolRequest) (resp *qscheduler.CreateSchedulerPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	if r.Config == nil {
		return nil, status.Errorf(codes.InvalidArgument, "missing config")
	}
	sp := types.QScheduler{
		SchedulerID: r.PoolId,
		Reconciler:  reconciler.New(),
		Scheduler:   scheduler.New(time.Now()),
		Config:      r.Config,
	}
	store := state.NewStore(r.PoolId)
	if err := store.Save(ctx, &sp); err != nil {
		return nil, err
	}
	return &qscheduler.CreateSchedulerPoolResponse{}, nil
}

// CreateAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateAccount(ctx context.Context, r *qscheduler.CreateAccountRequest) (resp *qscheduler.CreateAccountResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	do := func(ctx context.Context) error {
		store := state.NewStore(r.PoolId)
		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}

		sp.Scheduler.AddAccount(ctx, scheduler.AccountID(r.AccountId), r.Config, nil)

		return store.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.CreateAccountResponse{}, nil
}

// Wipe implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) Wipe(ctx context.Context, r *qscheduler.WipeRequest) (resp *qscheduler.WipeResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	do := func(ctx context.Context) error {
		store := state.NewStore(r.PoolId)
		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}
		sp.Scheduler = scheduler.New(time.Now())
		sp.Reconciler = reconciler.New()
		return store.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.WipeResponse{}, nil
}

// ListAccounts implements QSchedulerAdminServer.
func (s *QSchedulerViewServerImpl) ListAccounts(ctx context.Context, r *qscheduler.ListAccountsRequest) (resp *qscheduler.ListAccountsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := state.NewStore(r.PoolId)
	sp, err := store.Load(ctx)
	if err != nil {
		return nil, err
	}
	// TODO(akeshet): Add API to Scheduler so we can decouple from the proto representation.
	sProto := sp.Scheduler.ToProto()
	resp = &qscheduler.ListAccountsResponse{
		Accounts: sProto.Config.AccountConfigs,
	}
	return resp, nil
}

// InspectPool implements QSchedulerAdminServer.
func (s *QSchedulerViewServerImpl) InspectPool(ctx context.Context, r *qscheduler.InspectPoolRequest) (resp *qscheduler.InspectPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := state.NewStore(r.PoolId)
	sp, err := store.Load(ctx)
	if err != nil {
		return nil, err
	}

	sProto := sp.Scheduler.ToProto()
	runningCount, idleCount := 0, 0
	running := make([]*qscheduler.InspectPoolResponse_RunningTask, 0, len(sProto.State.Workers))
	idle := make([]*qscheduler.InspectPoolResponse_IdleBot, 0, len(sProto.State.Workers))
	for wid, w := range sProto.State.Workers {
		if w.RunningTask != nil {
			runningCount++
			running = append(running, &qscheduler.InspectPoolResponse_RunningTask{
				BotId:     wid,
				Id:        w.RunningTask.RequestId,
				Priority:  w.RunningTask.Priority,
				AccountId: w.RunningTask.Request.AccountId,
			})
		} else {
			idleCount++
			idle = append(idle, &qscheduler.InspectPoolResponse_IdleBot{
				Id:         wid,
				Dimensions: w.Labels,
			})
		}
	}

	waiting := make([]*qscheduler.InspectPoolResponse_WaitingTask, 0, len(sProto.State.QueuedRequests))
	for rid, r := range sProto.State.QueuedRequests {
		waiting = append(waiting, &qscheduler.InspectPoolResponse_WaitingTask{
			Id:        rid,
			AccountId: r.AccountId,
		})
	}

	resp = &qscheduler.InspectPoolResponse{
		NumWaitingTasks: int32(len(sProto.State.QueuedRequests)),
		NumIdleBots:     int32(idleCount),
		NumRunningTasks: int32(runningCount),
		RunningTasks:    running,
		WaitingTasks:    waiting,
		IdleBots:        idle,
		AccountBalances: sProto.State.Balances,
	}

	return resp, nil
}
