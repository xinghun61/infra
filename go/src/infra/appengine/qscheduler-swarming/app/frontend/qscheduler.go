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
	"math/rand"

	"infra/appengine/qscheduler-swarming/app/state"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	"infra/appengine/qscheduler-swarming/app/state/operations"
	swarming "infra/swarming"

	"go.chromium.org/luci/grpc/grpcutil"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// BasicQSchedulerServer implements the QSchedulerServer interface.
//
// This implementation is only expected to scale to ~1QPS of mutating
// operations, because it handles each request in its own datastore
// transaction.
type BasicQSchedulerServer struct{}

// AssignTasks implements QSchedulerServer.
func (s *BasicQSchedulerServer) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (resp *swarming.AssignTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	dur := getHandlerTimeout(ctx)
	var cancel context.CancelFunc
	if dur != 0 {
		ctx, cancel = context.WithTimeout(ctx, dur)
		defer cancel()
	}

	op, result := operations.AssignTasks(r)

	store := nodestore.New(r.SchedulerId)
	if err = store.Run(ctx, state.NewNodeStoreOperationRunner(op, r.SchedulerId)); err != nil {
		return nil, err
	}

	return result, err
}

// GetCancellations implements QSchedulerServer.
func (s *BasicQSchedulerServer) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (resp *swarming.GetCancellationsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err = r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	store := nodestore.New(r.SchedulerId)
	sp, err := store.Get(ctx)
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
func (s *BasicQSchedulerServer) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (resp *swarming.NotifyTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	if err := r.Validate(); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}

	dur := getHandlerTimeout(ctx)
	var cancel context.CancelFunc
	if dur != 0 {
		ctx, cancel = context.WithTimeout(ctx, dur)
		defer cancel()
	}

	op, result := operations.NotifyTasks(r)

	store := nodestore.New(r.SchedulerId)
	if err = store.Run(ctx, state.NewNodeStoreOperationRunner(op, r.SchedulerId)); err != nil {
		return nil, err
	}
	return result, nil
}

// GetCallbacks implements QSchedulerServer.
func (s *BasicQSchedulerServer) GetCallbacks(ctx context.Context, r *swarming.GetCallbacksRequest) (resp *swarming.GetCallbacksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	store := nodestore.New(r.SchedulerId)
	sp, err := store.Get(ctx)
	if err != nil {
		return nil, err
	}

	var requestIDs []string

	// TODO(akeshet): Select the N% most stale items, rather than 5% of tasks
	// with uniform randomness.
	for rid := range sp.Scheduler.GetWaitingRequests() {
		if rand.Int31n(100) == 0 {
			requestIDs = append(requestIDs, string(rid))
		}
	}
	for _, w := range sp.Scheduler.GetWorkers() {
		if !w.IsIdle() {
			if rand.Int31n(100) <= 4 {
				requestIDs = append(requestIDs, string(w.RunningRequest().ID))
			}
		}
	}

	resp = &swarming.GetCallbacksResponse{
		TaskIds: requestIDs,
	}

	return resp, nil
}
