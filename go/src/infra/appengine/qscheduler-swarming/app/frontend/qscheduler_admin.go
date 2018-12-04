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

	"github.com/pkg/errors"

	"go.chromium.org/gae/service/datastore"
	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/entities"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

// QSchedulerAdminServerImpl implements QSchedulerAdminServer.
type QSchedulerAdminServerImpl struct{}

// CreateSchedulerPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateSchedulerPool(ctx context.Context, r *qscheduler.CreateSchedulerPoolRequest) (*qscheduler.CreateSchedulerPoolResponse, error) {
	if r.Config == nil {
		return nil, errors.Errorf("Missing config.")
	}
	sp := entities.QSchedulerState{
		SchedulerID: r.PoolId,
		Reconciler:  reconciler.New(),
		Scheduler:   scheduler.New(time.Now()),
		Config:      r.Config,
	}
	if err := entities.Save(ctx, &sp); err != nil {
		return nil, err
	}
	return &qscheduler.CreateSchedulerPoolResponse{}, nil
}

// CreateAccount implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) CreateAccount(ctx context.Context, r *qscheduler.CreateAccountRequest) (*qscheduler.CreateAccountResponse, error) {
	do := func(ctx context.Context) error {
		sp, err := entities.Load(ctx, r.PoolId)
		if err != nil {
			return err
		}
		if err := sp.Scheduler.AddAccount(ctx, r.AccountId, r.Config, nil); err != nil {
			return err
		}
		return entities.Save(ctx, sp)
	}

	if err := datastore.RunInTransaction(ctx, do, nil); err != nil {
		return nil, err
	}
	return &qscheduler.CreateAccountResponse{}, nil
}

// ListAccounts implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) ListAccounts(ctx context.Context, r *qscheduler.ListAccountsRequest) (*qscheduler.ListAccountsResponse, error) {
	sp, err := entities.Load(ctx, r.PoolId)
	if err != nil {
		return nil, err
	}
	resp := &qscheduler.ListAccountsResponse{
		Accounts: sp.Scheduler.Config.AccountConfigs,
	}
	return resp, nil
}

// InspectPool implements QSchedulerAdminServer.
func (s *QSchedulerAdminServerImpl) InspectPool(ctx context.Context, r *qscheduler.InspectPoolRequest) (*qscheduler.InspectPoolResponse, error) {
	sp, err := load(ctx, r.PoolId)
	if err != nil {
		return nil, err
	}

	running, idle := 0, 0
	for _, w := range sp.scheduler.State.Workers {
		if w.RunningTask != nil {
			running++
		} else {
			idle++
		}
	}

	resp := &qscheduler.InspectPoolResponse{
		WaitingTasks:    int32(len(sp.scheduler.State.QueuedRequests)),
		IdleBots:        int32(idle),
		RunningTasks:    int32(running),
		AccountBalances: sp.scheduler.State.Balances,
	}

	return resp, nil
}
