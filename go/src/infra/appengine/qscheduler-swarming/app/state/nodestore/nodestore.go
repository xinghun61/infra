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

// Package nodestore implements a datastore-backed persistent store of qscheduler
// state, that shards state over as many entities as necessary to stay under datastore's
// single-entity size limit, and uses an in-memory cache to avoid unnecessary
// datastore reads.
package nodestore

import (
	"bytes"
	"context"
	"sync"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/google/uuid"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"

	"infra/appengine/qscheduler-swarming/app/state/nodestore/internal/blob"
	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

var errWrongGeneration = errors.New("wrong generation")

type stateAndGeneration struct {
	state      *blob.QSchedulerPoolState
	generation int64
}

// Operator describes an interface that NodeStore will use for for mutating a
// quotascheduler's state, and persisting any side-effects.
//
// NodeStore will not call any methods of an Operator concurrently.
type Operator interface {
	// Modify is called to modify a quotascheduler state; it may be called
	// more than once, therefore it should not have side effects besides:
	// any side effects other than:
	// - modifying the supplied *types.QScheduler,
	// - side effects that are stored internally to the Operator (e.g. metrics
	// to be used in the Commit or Finish calls).
	//
	// If there are any side effects stored internally to the Operator, they
	// should be reset on each call to Modify.
	Modify(ctx context.Context, state *types.QScheduler) error

	// Commit will be called within a datastore transaction, after a successful
	// call to Modify. Commit should be used to persist any transactional
	// side effects of Modify (such as emitting tasks to a task queue).
	Commit(context.Context) error

	// Finish will be called at most once, after a successful call to Commit.
	// This will be called outside of any transactions, and should be used
	// for non-transactional at-most-once side effects, such as incrementing
	// ts_mon counters.
	Finish(context.Context)
}

type modOnlyOperator struct {
	mod func(ctx context.Context, state *types.QScheduler) error
}

var _ Operator = modOnlyOperator{}

func (m modOnlyOperator) Modify(ctx context.Context, state *types.QScheduler) error {
	return m.mod(ctx, state)
}

func (m modOnlyOperator) Commit(ctx context.Context) error { return nil }

func (m modOnlyOperator) Finish(ctx context.Context) {}

// NewModOnlyOperator returns an Operator that simply applies the given state-modification
// function. This is a convenience method for callers that don't need to handle
// the Commit or Finish phases of an Operator.
func NewModOnlyOperator(f func(ctx context.Context, state *types.QScheduler) error) Operator {
	return modOnlyOperator{f}
}

// New returns a new NodeStore.
func New(qsPoolID string) *NodeStore {
	return &NodeStore{qsPoolID: qsPoolID}
}

// List returns the full list of scheduler ids.
func List(ctx context.Context) ([]string, error) {
	var keys []*datastore.Key
	query := datastore.NewQuery("stateRecord")
	if err := datastore.GetAll(ctx, query, &keys); err != nil {
		return nil, errors.Annotate(err, "nodestore list").Err()
	}

	IDs := make([]string, len(keys))
	for i, item := range keys {
		IDs[i] = item.StringID()
	}
	return IDs, nil
}

// NodeStore is a persistent store for an individual quotascheduler state.
//
// All methods are concurrency-safe.
type NodeStore struct {
	qsPoolID string

	cacheLock sync.RWMutex
	cache     *stateAndGeneration
}

// Create creates a new persistent scheduler entity if one doesn't exist.
func (n *NodeStore) Create(ctx context.Context, timestamp time.Time) error {
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		record := &stateRecord{PoolID: n.qsPoolID}
		exists, err := datastore.Exists(ctx, record)
		if err != nil {
			return err
		}
		if exists.Any() {
			return errors.Reason("entity already exists").Err()
		}

		s := scheduler.New(timestamp)
		r := reconciler.New()
		p := &blob.QSchedulerPoolState{
			Scheduler:  s.ToProto(),
			Reconciler: r.ToProto(),
		}
		nodeIDs, err := writeNodes(ctx, p, n.qsPoolID, 0)
		if err != nil {
			return err
		}
		record.NodeIDs = nodeIDs
		return datastore.Put(ctx, record)
	}, &datastore.TransactionOptions{XG: true})
	if err != nil {
		return errors.Annotate(err, "nodestore create").Err()
	}
	return nil
}

// Run runs the given operator.
func (n *NodeStore) Run(ctx context.Context, o Operator) error {
	sg := n.getCached()
	// Fast path; use in-memory cache to avoid reading state from datastore.
	if sg != nil {
		err := n.tryRun(ctx, o, sg)
		switch {
		case err == nil:
			o.Finish(ctx)
			return nil
		case errors.Contains(err, errWrongGeneration):
			// In-memory cache was wrong generation; try slow path.
		default:
			return errors.Annotate(err, "nodestore run").Err()
		}
	}

	for i := 0; i < 10; i++ {
		// Slow path; read full state from datastore, then follow usual modification
		// flow.
		sg, err := n.loadState(ctx)
		if err != nil {
			return errors.Annotate(err, "nodestore run").Err()
		}

		err = n.tryRun(ctx, o, sg)
		switch {
		case err == nil:
			o.Finish(ctx)
			return nil
		case errors.Contains(err, errWrongGeneration):
			// Contention against some other writer; try again.
		default:
			return errors.Annotate(err, "nodestore run").Err()
		}
	}

	return errors.New("nodestore run: too many attempts")
}

// Get returns the current qscheduler state.
func (n *NodeStore) Get(ctx context.Context) (*types.QScheduler, error) {
	sg, err := n.loadState(ctx)
	if err != nil {
		return nil, errors.Annotate(err, "nodestore get").Err()
	}

	return &types.QScheduler{
		Reconciler: reconciler.NewFromProto(sg.state.Reconciler),
		Scheduler:  scheduler.NewFromProto(sg.state.Scheduler),
	}, nil
}

// Clean deletes stale entities. It should be called periodically by a cronjob.
//
// It returns the number of stale entities deleted.
func (n *NodeStore) Clean(ctx context.Context) (int, error) {
	sg, err := n.loadState(ctx)
	if err != nil {
		return 0, errors.Annotate(err, "nodestore clean").Err()
	}

	// Cleanup nodes that are more than 100 generations old.
	// Don't delete ones more recent than that, to avoid killing concurrent loadState
	// calls from old generations.
	query := datastore.NewQuery("stateNode").Eq("PoolID", n.qsPoolID).Lt("Generation", sg.generation-100)

	var keys []*datastore.Key
	if err := datastore.GetAll(ctx, query, &keys); err != nil {
		return 0, errors.Annotate(err, "nodestore clean").Err()
	}

	if err = datastore.Delete(ctx, keys); err != nil {
		return 0, errors.Annotate(err, "nodestore clean").Err()
	}

	return len(keys), nil
}

// Delete deletes all entities associated with a given pool.
func (n *NodeStore) Delete(ctx context.Context) error {
	record := &stateRecord{
		PoolID: n.qsPoolID,
	}

	exists, err := datastore.Exists(ctx, record)
	if err != nil {
		return errors.Annotate(err, "nodestore delete").Err()
	}
	// Only try deleting top level record if it exists.
	if exists.Any() {
		if err := datastore.Delete(ctx, record); err != nil {
			return errors.Annotate(err, "nodestore delete").Err()
		}
	}

	query := datastore.NewQuery("stateNode").Eq("PoolID", n.qsPoolID)
	var keys []*datastore.Key
	if err := datastore.GetAll(ctx, query, &keys); err != nil {
		return errors.Annotate(err, "nodestore delete").Err()
	}

	if err := datastore.Delete(ctx, keys); err != nil {
		return errors.Annotate(err, "nodestore delete").Err()
	}

	return nil
}

// tryRun attempts to modify and commit the given state, using the given operator.
func (n *NodeStore) tryRun(ctx context.Context, o Operator, sg *stateAndGeneration) error {
	q := &types.QScheduler{
		SchedulerID: n.qsPoolID,
		Reconciler:  reconciler.NewFromProto(sg.state.Reconciler),
		Scheduler:   scheduler.NewFromProto(sg.state.Scheduler),
	}
	if err := o.Modify(ctx, q); err != nil {
		return errors.Annotate(err, "nodestore try").Err()
	}
	p := &blob.QSchedulerPoolState{
		Reconciler: q.Reconciler.ToProto(),
		Scheduler:  q.Scheduler.ToProto(),
	}
	IDs, err := writeNodes(ctx, p, n.qsPoolID, sg.generation+1)
	if err != nil {
		return errors.Annotate(err, "nodestore try").Err()
	}

	err = datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		record := &stateRecord{PoolID: n.qsPoolID}
		if err := datastore.Get(ctx, record); err != nil {
			return err
		}

		if record.Generation != sg.generation {
			// Supplied generation was out of date.
			return errWrongGeneration
		}

		outRecord := &stateRecord{
			PoolID:     n.qsPoolID,
			NodeIDs:    IDs,
			Generation: sg.generation + 1,
		}
		if err := datastore.Put(ctx, outRecord); err != nil {
			return err
		}

		return o.Commit(ctx)
	}, nil)

	if err != nil {
		return errors.Annotate(err, "nodestore try").Err()
	}

	n.setCached(&stateAndGeneration{p, sg.generation + 1})
	return nil
}

func (n *NodeStore) getCached() *stateAndGeneration {
	n.cacheLock.RLock()
	s := n.cache
	n.cacheLock.RUnlock()
	return s
}

func (n *NodeStore) setCached(sg *stateAndGeneration) {
	n.cacheLock.Lock()
	if n.cache == nil || sg.generation > n.cache.generation {
		n.cache = sg
	}
	n.cacheLock.Unlock()
}

func (n *NodeStore) loadState(ctx context.Context) (*stateAndGeneration, error) {
	record := &stateRecord{PoolID: n.qsPoolID}
	if err := datastore.Get(ctx, record); err != nil {
		return nil, errors.Annotate(err, "nodestore load").Err()
	}

	state, err := loadNodes(ctx, record.NodeIDs)
	if err != nil {
		return nil, errors.Annotate(err, "nodestore load").Err()
	}

	return &stateAndGeneration{state: state, generation: record.Generation}, nil
}

type stateRecord struct {
	_kind string `gae:"$kind,stateRecord"`

	// PoolID is the qs pool ID for this record.
	PoolID string `gae:"$id"`

	Generation int64 `gae:",noindex"`

	NodeIDs []string `gae:",noindex"`
}

// stateNode is the datastore entity used to represent a shard of
// quotascheduler state.
//
// TODO(akeshet): Add a cleanup mechanism that removes stale graph entities.
type stateNode struct {
	_kind string `gae:"$kind,stateNode"`

	// ID is a globally unique ID for this entity. Entities are append-only.
	ID string `gae:"$id"`

	// PoolID is the ID of the pool that this node corresponds to. It is an
	// indexed field, used to enable cleanup of stale entities.
	PoolID string `gae:"PoolID"`

	// Generation is the generation number of the parent state for which
	// this entity was written. It is an indexed field, used to enable cleanup
	// of stale entities.
	Generation int64 `gae:"Generation"`

	// QSchedulerPoolStateDataShard contains this node's shard of the proto-
	// serialized QSchedulerPoolState.
	QSchedulerPoolStateDataShard []byte `gae:",noindex"`
}

// writeNodes writes the given state to as many nodes as necessary, and returns
// their IDs.
func writeNodes(ctx context.Context, state *blob.QSchedulerPoolState, poolID string, generation int64) ([]string, error) {
	bytes, err := proto.Marshal(state)
	if err != nil {
		return nil, errors.Annotate(err, "write nodes").Err()
	}

	// TODO(akeshet): Tune this for a good balance between staying safely below
	// upper limit and using fewer shards.
	maxBytes := 900000
	var shards [][]byte
	for offset := 0; offset < len(bytes); offset += maxBytes {
		start := offset
		end := start + maxBytes
		if end > len(bytes) {
			end = len(bytes)
		}
		shards = append(shards, bytes[start:end])
	}

	nodes := make([]interface{}, len(shards))
	IDs := make([]string, len(shards))
	for i, shard := range shards {
		ID := uuid.New().String()
		node := &stateNode{
			ID:                           ID,
			PoolID:                       poolID,
			Generation:                   generation,
			QSchedulerPoolStateDataShard: shard,
		}

		nodes[i] = node
		IDs[i] = ID
	}

	if err := datastore.Put(ctx, nodes...); err != nil {
		return nil, errors.Annotate(err, "write nodes").Err()
	}

	return IDs, nil
}

// loadNodes loads state from the given set of nodes.
func loadNodes(ctx context.Context, nodeIDs []string) (*blob.QSchedulerPoolState, error) {
	nodes := make([]interface{}, len(nodeIDs))
	for i, ID := range nodeIDs {
		nodes[i] = &stateNode{ID: ID}
	}

	if err := datastore.Get(ctx, nodes...); err != nil {
		return nil, err
	}

	var buffer bytes.Buffer
	for _, n := range nodes {
		node, ok := n.(*stateNode)
		if !ok {
			return nil, errors.New("load nodes: unexpected node type")
		}

		if _, err := buffer.Write(node.QSchedulerPoolStateDataShard); err != nil {
			return nil, errors.Annotate(err, "load nodes").Err()
		}
	}

	state := blob.QSchedulerPoolState{}
	if err := proto.Unmarshal(buffer.Bytes(), &state); err != nil {
		return nil, err
	}

	return &state, nil
}
