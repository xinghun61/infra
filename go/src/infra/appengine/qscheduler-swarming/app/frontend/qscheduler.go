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

	"infra/appengine/qscheduler-swarming/app/frontend/internal/operations"
	"infra/appengine/qscheduler-swarming/app/state"
	swarming "infra/swarming"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/grpc/grpcutil"

	"infra/qscheduler/qslib/scheduler"
)

// WorkerID is a type alias for WorkerID
type WorkerID = scheduler.WorkerID

// RequestID is a type alias for RequestID
type RequestID = scheduler.RequestID

// AccountID is a type alias for AccountID
type AccountID = scheduler.AccountID

// QSchedulerServerImpl implements the QSchedulerServer interface.
//
// This implementation is only expected to scale to ~1QPS of mutating
// operations, because it handles each request in its own datastore
// transaction.
type QSchedulerServerImpl struct{}

// singleOperationRunner returns a read-modify-write function for an operation.
//
// The returned function is suitable to be used with
// datastore.RunInTransaction.
func singleOperationRunner(op operations.Operation, schedulerID string) func(context.Context) error {
	return func(ctx context.Context) error {
		store := state.NewStore(schedulerID)
		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}

		if err = op(ctx, sp); err != nil {
			return err
		}

		if err := store.Save(ctx, sp); err != nil {
			return err
		}

		return nil
	}
}

// AssignTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (resp *swarming.AssignTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	op, result := operations.AssignTasks(r)

	if err := datastore.RunInTransaction(ctx, singleOperationRunner(op, r.SchedulerId), nil); err != nil {
		return nil, err
	}

	return result.Response, result.Error
}

// GetCancellations implements QSchedulerServer.
func (s *QSchedulerServerImpl) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (resp *swarming.GetCancellationsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := state.NewStore(r.SchedulerId)
	sp, err := store.Load(ctx)
	if err != nil {
		return nil, err
	}

	c := sp.Reconciler.Cancellations(ctx)
	rc := make([]*swarming.GetCancellationsResponse_Cancellation, len(c))
	for i, v := range c {
		rc[i] = &swarming.GetCancellationsResponse_Cancellation{BotId: v.WorkerID, TaskId: v.RequestID}
	}
	return &swarming.GetCancellationsResponse{Cancellations: rc}, nil
}

// NotifyTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (resp *swarming.NotifyTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	op, result := operations.NotifyTasks(r)

	if err := datastore.RunInTransaction(ctx, singleOperationRunner(op, r.SchedulerId), nil); err != nil {
		return nil, err
	}
	return result.Response, result.Error
}
