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

	"github.com/pkg/errors"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/qscheduler/qslib/reconciler"
	"infra/qscheduler/qslib/scheduler"
)

const stateEntityKind = "qschedulerStateEntity"

// qschedulerStateEntity is the datastore entity used to store state for a given
// qscheduler pool, in a few protobuf binaries.
type qschedulerStateEntity struct {
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

// save persists the given SchdulerPool to datastore.
func save(ctx context.Context, q *QSchedulerState) error {
	var sd, rd []byte
	var err error
	if sd, err = proto.Marshal(q.scheduler); err != nil {
		e := errors.Wrap(err, "unable to marshal Scheduler")
		return status.Error(codes.Internal, e.Error())
	}

	if rd, err = proto.Marshal(q.reconciler); err != nil {
		e := errors.Wrap(err, "unable to marshal Reconciler")
		return status.Error(codes.Internal, e.Error())
	}

	entity := &qschedulerStateEntity{
		QSPoolID:       q.schedulerID,
		SchedulerData:  sd,
		ReconcilerData: rd,
	}

	if err := datastore.Put(ctx, entity); err != nil {
		e := errors.Wrap(err, "unable to Put scheduler state")
		return status.Error(codes.Internal, e.Error())
	}

	return nil
}

// load loads the SchedulerPool with the given id from datastore and returns it.
func load(ctx context.Context, poolID string) (*QSchedulerState, error) {
	dst := &qschedulerStateEntity{QSPoolID: poolID}
	if err := datastore.Get(ctx, dst); err != nil {
		e := errors.Wrap(err, "unable to get state entity")
		return nil, status.Error(codes.NotFound, e.Error())
	}

	r := new(reconciler.State)
	s := new(scheduler.Scheduler)
	if err := proto.Unmarshal(dst.ReconcilerData, r); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Reconciler")
	}
	if err := proto.Unmarshal(dst.SchedulerData, s); err != nil {
		return nil, errors.Wrap(err, "unable to unmarshal Scheduler")
	}

	return &QSchedulerState{
		schedulerID: dst.QSPoolID,
		reconciler:  r,
		scheduler:   s,
	}, nil
}
