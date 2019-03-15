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

type configSet struct {
	_kind   string `gae:"$kind,droneConfigSet"`
	ID      string `gae:"$id"`
	Updated time.Time
}

// Entity is a drone config datastore entity.
type Entity struct {
	_kind     string         `gae:"$kind,droneConfig"`
	Hostname  string         `gae:"$id"`
	ConfigSet *datastore.Key `gae:"$parent"`
	DUTs      []DUT          `gae:",noindex"`
}

// DUT describes a DUT for the purposes of a drone config.
type DUT struct {
	ID       string
	Hostname string
}

// latestSetID is the configSet ID used for the latest config set.
const latestSetID = "latest"

// Update updates drone configs in datastore.  This update happens
// atomically, as the entire set of drone configs should be consistent
// so a DUT doesn't get assigned to two drones.  The ConfigSet field
// on the entities passed in may be modified.
func Update(ctx context.Context, entities []Entity) error {
	err := datastore.RunInTransaction(ctx, func(ctx context.Context) error {
		s := configSet{
			ID:      latestSetID,
			Updated: time.Now().UTC(),
		}
		if err := datastore.Put(ctx, &s); err != nil {
			return err
		}
		k := datastore.KeyForObj(ctx, &s)
		for i := range entities {
			entities[i].ConfigSet = k
		}
		return datastore.Put(ctx, entities)
	}, nil)
	if err != nil {
		return errors.Annotate(err, "update drone configs").Err()
	}
	return nil
}

// Get gets a drone config from datastore by hostname.
func Get(ctx context.Context, hostname string) (Entity, error) {
	e := Entity{
		Hostname:  hostname,
		ConfigSet: datastore.NewKey(ctx, "droneConfigSet", latestSetID, 0, nil),
	}
	if err := datastore.Get(ctx, &e); err != nil {
		return e, errors.Annotate(err, "get drone config").Err()
	}
	return e, nil
}
