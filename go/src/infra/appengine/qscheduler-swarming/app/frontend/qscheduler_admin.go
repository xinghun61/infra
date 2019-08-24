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

	"go.chromium.org/luci/grpc/grpcutil"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"
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

	if r.Config != nil {
		return nil, status.Errorf(codes.InvalidArgument, "Config argument deprecated")
	}

	store := nodestore.New(r.PoolId)
	if err := store.Create(ctx, time.Now()); err != nil {
		return nil, err
	}
	return &qscheduler.CreateSchedulerPoolResponse{}, nil
}

// CreateAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateAccount(ctx context.Context, r *qscheduler.CreateAccountRequest) (resp *qscheduler.CreateAccountResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	var ac *scheduler.AccountConfig
	if r.Config != nil {
		ac = scheduler.NewAccountConfigFromProto(r.Config)
	} else {
		ac = &scheduler.AccountConfig{}
	}

	store := nodestore.New(r.PoolId)
	op := nodestore.NewModOnlyOperator(func(ctx context.Context, state *types.QScheduler) error {
		state.Scheduler.AddAccount(ctx, scheduler.AccountID(r.AccountId), ac, nil)
		return nil
	})
	if err := store.Run(ctx, op); err != nil {
		return nil, err
	}

	return &qscheduler.CreateAccountResponse{}, nil
}

// Wipe implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) Wipe(ctx context.Context, r *qscheduler.WipeRequest) (resp *qscheduler.WipeResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	op := nodestore.NewModOnlyOperator(func(ctx context.Context, sp *types.QScheduler) error {
		config := sp.Scheduler.Config()
		sp.Scheduler = scheduler.NewWithConfig(time.Now(), config)
		sp.Reconciler = reconciler.New()
		return nil
	})
	if err := store.Run(ctx, op); err != nil {
		return nil, err
	}

	return &qscheduler.WipeResponse{}, nil
}

// ModAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ModAccount(ctx context.Context, r *qscheduler.ModAccountRequest) (resp *qscheduler.ModAccountResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	op := nodestore.NewModOnlyOperator(func(ctx context.Context, sp *types.QScheduler) error {
		config := sp.Scheduler.Config()
		accountConfig, ok := config.AccountConfigs[scheduler.AccountID(r.AccountId)]
		if !ok {
			return status.Errorf(codes.NotFound, "no account with id %s", r.AccountId)
		}

		if r.MaxChargeSeconds != nil {
			accountConfig.MaxChargeSeconds = r.MaxChargeSeconds.Value
		}
		if r.MaxFanout != nil {
			accountConfig.MaxFanout = r.MaxFanout.Value
		}
		if r.DisableFreeTasks != nil {
			accountConfig.DisableFreeTasks = r.DisableFreeTasks.Value
		}
		if len(r.ChargeRate) != 0 {
			bal := scheduler.Balance{}
			copy(bal[:], r.ChargeRate)
			accountConfig.ChargeRate = bal
		}
		return nil
	})
	if err := store.Run(ctx, op); err != nil {
		return nil, err
	}

	return &qscheduler.ModAccountResponse{}, nil
}

// ModSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ModSchedulerPool(ctx context.Context, r *qscheduler.ModSchedulerPoolRequest) (resp *qscheduler.ModSchedulerPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	op := nodestore.NewModOnlyOperator(func(ctx context.Context, sp *types.QScheduler) error {
		config := sp.Scheduler.Config()
		if r.DisablePreemption != nil {
			config.DisablePreemption = r.DisablePreemption.Value
		}
		if r.BotExpirationSeconds != nil {
			config.BotExpiration = time.Duration(r.BotExpirationSeconds.Value) * time.Second
		}

		return nil
	})

	if err := store.Run(ctx, op); err != nil {
		return nil, err
	}

	return &qscheduler.ModSchedulerPoolResponse{}, nil
}

// DeleteAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) DeleteAccount(ctx context.Context, r *qscheduler.DeleteAccountRequest) (resp *qscheduler.DeleteAccountResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	op := nodestore.NewModOnlyOperator(func(ctx context.Context, sp *types.QScheduler) error {
		sp.Scheduler.DeleteAccount(scheduler.AccountID(r.AccountId))
		return nil
	})

	if err := store.Run(ctx, op); err != nil {
		return nil, err
	}

	return &qscheduler.DeleteAccountResponse{}, nil
}

// DeleteSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) DeleteSchedulerPool(ctx context.Context, r *qscheduler.DeleteSchedulerPoolRequest) (resp *qscheduler.DeleteSchedulerPoolResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	if err := store.Delete(ctx); err != nil {
		return nil, err
	}

	return &qscheduler.DeleteSchedulerPoolResponse{}, nil
}

// ListAccounts implements QSchedulerAdminServer.
func (s *QSchedulerViewServerImpl) ListAccounts(ctx context.Context, r *qscheduler.ListAccountsRequest) (resp *qscheduler.ListAccountsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.PoolId)
	sp, err := store.Get(ctx)
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
