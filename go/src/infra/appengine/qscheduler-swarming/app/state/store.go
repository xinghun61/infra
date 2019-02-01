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

	"github.com/pkg/errors"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/logging"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

const stateEntityKind = "qschedulerStateEntity"

// datastoreEntity is the datastore entity used to store state for a given
// qscheduler pool, in a few protobuf binaries.
type datastoreEntity struct {
	_kind string `gae:"$kind,qschedulerStateEntity"`

	QSPoolID string `gae:"$id"`

	// SchedulerData is the qslib/scheduler.Scheduler object serialized to
	// protobuf binary format.
	SchedulerData []byte `gae:",noindex"`

	// ReconcilerData is the qslib/reconciler.State object serialized to protobuf
	// binary format.
	ReconcilerData []byte `gae:",noindex"`

	// ConfigData is the SchedulerPoolConfig object, serialized to protobuf
	// binary format.
	ConfigData []byte `gae:",noindex"`
}

// Store implements a persistent store for QScheduler state.
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
func (s *Store) Save(ctx context.Context, q *QScheduler) error {
	var sd, rd, cd []byte
	var err error
	if sd, err = proto.Marshal(q.Scheduler.ToProto()); err != nil {
		e := errors.Wrap(err, "unable to marshal Scheduler")
		return status.Error(codes.Internal, e.Error())
	}

	if rd, err = proto.Marshal(q.Reconciler); err != nil {
		e := errors.Wrap(err, "unable to marshal Reconciler")
		return status.Error(codes.Internal, e.Error())
	}

	if cd, err = proto.Marshal(q.Config); err != nil {
		e := errors.Wrap(err, "unable to marshal Config")
		return status.Error(codes.Internal, e.Error())
	}

	entity := &datastoreEntity{
		QSPoolID:       s.entityID,
		SchedulerData:  sd,
		ReconcilerData: rd,
		ConfigData:     cd,
	}

	logging.Infof(ctx, "attempting to Put datastore entitiy for pool %s"+
		"with (Scheduler, Reconciler, Config) size of (%d, %d, %d) bytes",
		entity.QSPoolID, len(entity.SchedulerData), len(entity.ReconcilerData),
		len(entity.ConfigData))

	if err := datastore.Put(ctx, entity); err != nil {
		e := errors.Wrap(err, "unable to Put scheduler state")
		return status.Error(codes.Internal, e.Error())
	}

	return nil
}

// Load loads the SchedulerPool with the given id from datastore and returns it.
func (s *Store) Load(ctx context.Context) (*QScheduler, error) {
	dst := &datastoreEntity{QSPoolID: s.entityID}
	if err := datastore.Get(ctx, dst); err != nil {
		e := errors.Wrap(err, "unable to get state entity")
		return nil, status.Error(codes.NotFound, e.Error())
	}

	r := new(reconciler.State)
	sp := new(scheduler.SchedulerProto)
	c := new(qscheduler.SchedulerPoolConfig)
	if err := proto.Unmarshal(dst.ReconcilerData, r); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Reconciler")
	}
	if err := proto.Unmarshal(dst.SchedulerData, sp); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Scheduler")
	}
	if err := proto.Unmarshal(dst.ConfigData, c); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Config")
	}

	return &QScheduler{
		SchedulerID: dst.QSPoolID,
		Reconciler:  r,
		Scheduler:   scheduler.NewFromProto(sp),
		Config:      c,
	}, nil
}
