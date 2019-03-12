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

// Package dronecfg implements datastore access for storing drone
// configs.
package dronecfg

import (
	"context"
	"time"

	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
)

// Entity is a drone config datastore entity.
type Entity struct {
	_kind    string `gae:"$kind,droneConfig"`
	Hostname string `gae:"$id"`
	Updated  time.Time
	DUTs     []DUT `gae:",noindex"`
}

// DUT describes a DUT for the purposes of a drone config.
type DUT struct {
	ID       string
	Hostname string
}

// Update updates drone configs in datastore.  This update happens
// atomically, as the entire set of drone configs should be consistent
// so a DUT doesn't get assigned to two drones.  The Updated field on
// the entities passed in is modified regardless of datastore errors.
func Update(ctx context.Context, entities []Entity) error {
	now := time.Now().UTC()
	for _, e := range entities {
		e.Updated = now
	}
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		return datastore.Put(ctx, entities)
	}, nil)
	if err != nil {
		return errors.Annotate(err, "update drone configs").Err()
	}
	return nil
}

// Get gets a drone config from datastore by hostname.
func Get(ctx context.Context, hostname string) (Entity, error) {
	var e Entity
	if err := datastore.Get(ctx, &e); err != nil {
		return e, errors.Annotate(err, "get drone config").Err()
	}
	return e, nil
}
