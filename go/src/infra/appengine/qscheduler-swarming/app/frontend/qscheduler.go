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

	"infra/appengine/qscheduler-swarming/app/state"
	"infra/appengine/qscheduler-swarming/app/state/operations"
	swarming "infra/swarming"

	"go.chromium.org/luci/grpc/grpcutil"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

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

// AssignTasks implements QSchedulerServer.
func (s *QSchedulerServerImpl) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (resp *swarming.AssignTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	op, result := operations.AssignTasks(r)

	store := state.NewStore(r.SchedulerId)
	if err := store.RunOperationInTransaction(ctx, op); err != nil {
		return nil, err
	}

	return result, err
}

// GetCancellations implements QSchedulerServer.
func (s *QSchedulerServerImpl) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (resp *swarming.GetCancellationsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

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
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	op, result := operations.NotifyTasks(r)

	store := state.NewStore(r.SchedulerId)
	if err := store.RunOperationInTransaction(ctx, op); err != nil {
		return nil, err
	}
	return result, nil
}
