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
	"bytes"
	"compress/zlib"
	"context"
	"io/ioutil"

	"github.com/pkg/errors"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/qscheduler-swarming/app/state/types"
	"infra/qscheduler/qslib/protos"
	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

// Store implements a persistent store for types.QScheduler state.
type Store struct {
	entityID string
}

// NewStore creates a new store.
func NewStore(entityID string) *Store {
	return &Store{entityID: entityID}
}

// List returns the full list of scheduler ids.
func List(ctx context.Context) ([]string, error) {
	query := datastore.NewQuery(stateEntityKind).KeysOnly(true)
	dst := []*datastore.Key{}
	if err := datastore.GetAll(ctx, query, &dst); err != nil {
		return nil, errors.Wrap(err, "unable to query for all scheduler keys")
	}

	ids := make([]string, 0, len(dst))
	for _, item := range dst {
		ids = append(ids, item.StringID())
	}
	return ids, nil
}

// Save persists the given SchdulerPool to datastore.
func (s *Store) Save(ctx context.Context, q *types.QScheduler) error {
	var sd, sdz, rd []byte
	var err error
	if sd, err = proto.Marshal(q.Scheduler.ToProto()); err != nil {
		e := errors.Wrap(err, "unable to marshal Scheduler")
		return status.Error(codes.Internal, e.Error())
	}
	if sdz, err = zlCompress(sd); err != nil {
		e := errors.Wrap(err, "unable to compress Scheduler")
		return status.Error(codes.Internal, e.Error())
	}

	if rd, err = proto.Marshal(q.Reconciler.ToProto()); err != nil {
		e := errors.Wrap(err, "unable to marshal Reconciler")
		return status.Error(codes.Internal, e.Error())
	}

	entity := &datastoreEntity{
		QSPoolID:        s.entityID,
		SchedulerDataZL: sdz,
		ReconcilerData:  rd,
	}

	logging.Infof(ctx, "attempting to Put datastore entitiy for pool %s"+
		"with (Scheduler, Reconciler) size of (%d, %d) bytes",
		entity.QSPoolID, len(entity.SchedulerData), len(entity.ReconcilerData))

	if err := datastore.Put(ctx, entity); err != nil {
		e := errors.Wrap(err, "unable to Put scheduler state")
		return status.Error(codes.Internal, e.Error())
	}

	return nil
}

// Load loads the SchedulerPool with the given id from datastore and returns it.
func (s *Store) Load(ctx context.Context) (*types.QScheduler, error) {
	dst := &datastoreEntity{QSPoolID: s.entityID}
	if err := datastore.Get(ctx, dst); err != nil {
		e := errors.Wrap(err, "unable to get state entity")
		return nil, status.Error(codes.NotFound, e.Error())
	}

	r := new(protos.Reconciler)
	sp := new(protos.Scheduler)
	if err := proto.Unmarshal(dst.ReconcilerData, r); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Reconciler")
	}

	var schedulerData []byte
	if len(dst.SchedulerData) > 0 {
		schedulerData = dst.SchedulerData
	} else if len(dst.SchedulerDataZL) > 0 {
		var err error
		schedulerData, err = zlDecompress(dst.SchedulerDataZL)
		if err != nil {
			return nil, errors.Wrap(err, "unable to decompress Scheduler")
		}
	}

	if err := proto.Unmarshal(schedulerData, sp); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Scheduler")
	}

	recordProtoSize(ctx, len(dst.ReconcilerData), dst.QSPoolID, "reconciler")
	recordProtoSize(ctx, len(dst.SchedulerData), dst.QSPoolID, "scheduler")
	recordProtoSize(ctx, len(dst.SchedulerDataZL), dst.QSPoolID, "scheduler_zlib")

	return &types.QScheduler{
		SchedulerID: dst.QSPoolID,
		Reconciler:  reconciler.NewFromProto(r),
		Scheduler:   scheduler.NewFromProto(sp),
	}, nil
}

// RunOperationInTransaction runs the given operation in a transaction on this store.
func (s *Store) RunOperationInTransaction(ctx context.Context, op types.Operation) error {
	e := newMetricsBuffer(s.entityID)
	if err := datastore.RunInTransaction(ctx, operationRunner(op, s, e), nil); err != nil {
		return err
	}
	return e.flushToTsMon(ctx)
}

// RunRevertableOperationInTransaction runs the given operation in a transaction on this store.
func (s *Store) RunRevertableOperationInTransaction(ctx context.Context, op types.RevertableOperation) error {
	e := newMetricsBuffer(s.entityID)
	if err := datastore.RunInTransaction(ctx, revertableOperationRunner(op, s, e), nil); err != nil {
		return err
	}
	return e.flushToTsMon(ctx)
}

const stateEntityKind = "qschedulerStateEntity"

// datastoreEntity is the datastore entity used to store state for a given
// qscheduler pool, in a few protobuf binaries.
type datastoreEntity struct {
	_kind string `gae:"$kind,qschedulerStateEntity"`

	QSPoolID string `gae:"$id"`

	// SchedulerData is the qslib/scheduler.Scheduler object serialized to
	// protobuf binary format.
	//
	// Only one of this or SchedulerDataZL should be specified.
	SchedulerData []byte `gae:",noindex"`

	// SchedulerDataZL is the the qslib/scheduler.Scheduler object serialized to
	// protobuf binary format and then zlib-compressed.
	//
	// Only one of this or SchedulerData should be specified.
	SchedulerDataZL []byte `gae:",noindex"`

	// ReconcilerData is the qslib/reconciler.State object serialized to protobuf
	// binary format.
	ReconcilerData []byte `gae:",noindex"`

	// ConfigData is the SchedulerPoolConfig object, serialized to protobuf
	// binary format.
	ConfigData []byte `gae:",noindex"`
}

// operationRunner returns a read-modify-write function for an operation.
//
// The returned function is suitable to be used with datastore.RunInTransaction.
func operationRunner(op types.Operation, store *Store, e *metricsBuffer) func(context.Context) error {
	return func(ctx context.Context) error {
		e.reset()

		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}

		if err = op(ctx, sp, e); err != nil {
			return err
		}

		if err := store.Save(ctx, sp); err != nil {
			return err
		}

		e.recordStateMetrics(sp.Scheduler)
		return e.flushToBQ(ctx)
	}
}

// revertableOperationRunner returns a read-modify-write function for a revertable operation.
//
// Revertable operations return a boolean to indicate that their mutations to state
// should be reverted rather than saved.
//
// The returned function is suitable to be used with datastore.RunInTransaction.
func revertableOperationRunner(op types.RevertableOperation, store *Store, e *metricsBuffer) func(context.Context) error {
	return func(ctx context.Context) error {
		e.reset()

		sp, err := store.Load(ctx)
		if err != nil {
			return err
		}

		revert := op(ctx, sp, e)
		if revert {
			return nil
		}

		if err := store.Save(ctx, sp); err != nil {
			return err
		}

		e.recordStateMetrics(sp.Scheduler)
		return e.flushToBQ(ctx)
	}
}

func zlCompress(input []byte) ([]byte, error) {
	buffer := &bytes.Buffer{}
	gzWriter := zlib.NewWriter(buffer)

	if _, err := gzWriter.Write(input); err != nil {
		return nil, errors.Wrap(err, "zlCompress")
	}
	if err := gzWriter.Close(); err != nil {
		return nil, errors.Wrap(err, "zlCompress")
	}

	return buffer.Bytes(), nil
}

func zlDecompress(input []byte) ([]byte, error) {
	gzReader, err := zlib.NewReader(bytes.NewReader(input))
	if err != nil {
		return nil, errors.Wrap(err, "zlDecompress")
	}
	defer gzReader.Close()

	output, err := ioutil.ReadAll(gzReader)
	if err != nil {
		return nil, errors.Wrap(err, "zlDecompress")
	}
	return output, nil
}
