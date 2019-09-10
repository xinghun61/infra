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

package state

import (
	"context"

	"infra/appengine/qscheduler-swarming/app/state/metrics"
	"infra/appengine/qscheduler-swarming/app/state/nodestore"
	"infra/appengine/qscheduler-swarming/app/state/types"
)

// NodeStoreOperationRunner is a nodestore.Operator implementation
// for state.Operation.
type NodeStoreOperationRunner struct {
	op     types.Operation
	mb     *metrics.Buffer
	poolID string
}

var _ nodestore.Operator = &NodeStoreOperationRunner{}

// Modify implements nodestore.Operator.
func (n *NodeStoreOperationRunner) Modify(ctx context.Context, qs *types.QScheduler) error {
	n.mb = metrics.NewBuffer(n.poolID)
	n.op(ctx, qs, n.mb)
	return nil
}

// Commit implements nodestore.Operator.
func (n *NodeStoreOperationRunner) Commit(ctx context.Context) error {
	// TODO(akeshet): Move this to Finish() once BigQuery events are re-enabled
	// for this app, because transactional emission of task queue items is
	// not supported from GKE runtime.
	return n.mb.FlushToBQ(ctx)
}

// Finish implements nodestore.Operator.
func (n *NodeStoreOperationRunner) Finish(ctx context.Context) {
	n.mb.FlushToTsMon(ctx)
}

// NewNodeStoreOperationRunner returns a new operation runner for the
// given operation.
func NewNodeStoreOperationRunner(op types.Operation, poolID string) *NodeStoreOperationRunner {
	return &NodeStoreOperationRunner{
		op:     op,
		poolID: poolID,
	}
}
