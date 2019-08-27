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
	"math/rand"
	"sync"

	"infra/appengine/qscheduler-swarming/app/state"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	"infra/appengine/qscheduler-swarming/app/state/operations"
	swarming "infra/swarming"

	"go.chromium.org/luci/grpc/grpcutil"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// BatchedQSchedulerServer implements the QSchedulerServer interface.
//
// This implementation batches concurrent read-write requests for a given
// scheduler.
type BatchedQSchedulerServer struct {
	// batchers is a map from scheduler id to batcher.
	batchers map[string]*state.BatchRunner

	// batchersLock governs access to batchers.
	batchersLock sync.RWMutex

	// TODO(akeshet): Add close / shutdown handlers.
}

// NewBatchedServer initializes a new BatchedQSchedulerServer
func NewBatchedServer() *BatchedQSchedulerServer {
	return &BatchedQSchedulerServer{
		batchers: make(map[string]*state.BatchRunner),
	}
}

// getOrCreateBatcher creates or returns the batcher for the given scheduler.
//
// Concurrency-safe.
func (s *BatchedQSchedulerServer) getOrCreateBatcher(schedulerID string) *state.BatchRunner {
	batcher, ok := s.getBatcher(schedulerID)
	if ok {
		return batcher
	}

	s.batchersLock.Lock()
	defer s.batchersLock.Unlock()

	batcher, ok = s.batchers[schedulerID]
	if ok {
		return batcher
	}
	batcher = state.NewBatcher(schedulerID)
	store := nodestore.New(schedulerID)
	// TODO(akeshet): close all started batchers in the server's close handler.
	batcher.Start(store)
	s.batchers[schedulerID] = batcher
	return batcher
}

// getBatcher returns the batcher for the given scheduler, if it exists.
//
// Concurrency-safe.
func (s *BatchedQSchedulerServer) getBatcher(schedulerID string) (*state.BatchRunner, bool) {
	s.batchersLock.RLock()
	defer s.batchersLock.RUnlock()

	batcher, ok := s.batchers[schedulerID]
	return batcher, ok
}

// AssignTasks implements QSchedulerServer.
func (s *BatchedQSchedulerServer) AssignTasks(ctx context.Context, r *swarming.AssignTasksRequest) (resp *swarming.AssignTasksResponse, err error) {
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

	op, result := operations.AssignTasks([]*swarming.AssignTasksRequest{r})

	batcher := s.getOrCreateBatcher(r.SchedulerId)
	wait := batcher.EnqueueOperation(ctx, op, state.BatchPriorityAssign)
	select {
	case err := <-wait:
		if err != nil {
			return nil, err
		}
		return result[0], nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

// GetCancellations implements QSchedulerServer.
func (s *BatchedQSchedulerServer) GetCancellations(ctx context.Context, r *swarming.GetCancellationsRequest) (resp *swarming.GetCancellationsResponse, err error) {
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
func (s *BatchedQSchedulerServer) NotifyTasks(ctx context.Context, r *swarming.NotifyTasksRequest) (resp *swarming.NotifyTasksResponse, err error) {
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

	batcher := s.getOrCreateBatcher(r.SchedulerId)
	wait := batcher.EnqueueOperation(ctx, op, state.BatchPriorityNotify)
	select {
	case err := <-wait:
		if err != nil {
			return nil, err
		}
		return result, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

// GetCallbacks implements QSchedulerServer.
func (s *BatchedQSchedulerServer) GetCallbacks(ctx context.Context, r *swarming.GetCallbacksRequest) (resp *swarming.GetCallbacksResponse, err error) {
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
