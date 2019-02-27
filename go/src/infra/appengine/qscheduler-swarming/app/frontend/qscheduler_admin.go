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
		Scheduler:   scheduler.NewWithConfig(time.Now(), r.Config),
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
		config := sp.Scheduler.Config()
		sp.Scheduler = scheduler.NewWithConfig(time.Now(), config)
		sp.Reconciler = reconciler.New()
		return store.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.WipeResponse{}, nil
}

// ModAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ModAccount(ctx context.Context, r *qscheduler.ModAccountRequest) (resp *qscheduler.ModAccountResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	do := func(ctx context.Context) error {
		store := state.NewStore(r.PoolId)
		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}
		config := sp.Scheduler.Config()
		accountConfig, ok := config.AccountConfigs[r.AccountId]
		if !ok {
			return status.Errorf(codes.NotFound, "no account with id %s", r.AccountId)
		}

		if r.MaxChargeSeconds != nil {
			accountConfig.MaxChargeSeconds = r.MaxChargeSeconds.Value
		}
		if r.MaxFanout != nil {
			accountConfig.MaxFanout = r.MaxFanout.Value
		}
		if len(r.ChargeRate) != 0 {
			accountConfig.ChargeRate = r.ChargeRate
		}
		return store.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.ModAccountResponse{}, nil
}

// ModSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ModSchedulerPool(ctx context.Context, r *qscheduler.ModSchedulerPoolRequest) (resp *qscheduler.ModSchedulerPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	do := func(ctx context.Context) error {
		store := state.NewStore(r.PoolId)
		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}
		config := sp.Scheduler.Config()
		if r.DisablePreemption != nil {
			config.DisablePreemption = r.DisablePreemption.Value
		}
		return store.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.ModSchedulerPoolResponse{}, nil
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
