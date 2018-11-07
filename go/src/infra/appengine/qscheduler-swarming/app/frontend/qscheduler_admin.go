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
	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

// QSchedulerAdminServerImpl implements QSchedulerAdminServer.
type QSchedulerAdminServerImpl struct{}

// CreateSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateSchedulerPool(ctx context.Context, r *qscheduler.CreateSchedulerPoolRequest) (*qscheduler.CreateSchedulerPoolResponse, error) {
	sp := QSchedulerState{
		schedulerID: r.PoolId,
		reconciler:  reconciler.New(),
		scheduler:   scheduler.New(time.Now()),
		config:      &qscheduler.SchedulerPoolConfig{},
	}
	if err := save(ctx, &sp); err != nil {
		return nil, err
	}
	return &qscheduler.CreateSchedulerPoolResponse{}, nil
}

// CreateAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateAccount(ctx context.Context, r *qscheduler.CreateAccountRequest) (*qscheduler.CreateAccountResponse, error) {
	do := func(ctx context.Context) error {
		sp, err := load(ctx, r.PoolId)
		if err != nil {
			return err
		}
		if err := sp.scheduler.AddAccount(ctx, r.AccountId, r.Config, nil); err != nil {
			return err
		}
		return save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.CreateAccountResponse{}, nil
}

// ListAccounts implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ListAccounts(ctx context.Context, r *qscheduler.ListAccountsRequest) (*qscheduler.ListAccountsResponse, error) {
	sp, err := load(ctx, r.PoolId)
	if err != nil {
		return nil, err
	}
	resp := &qscheduler.ListAccountsResponse{
		Accounts: sp.scheduler.Config.AccountConfigs,
	}
	return resp, nil
}
