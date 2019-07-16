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

package inventory

import (
	"context"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/libs/skylab/inventory"
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/google"
)

const (
	cachedInventoryDutKind = "cachedInventoryDut"
	cacheValidityDuration  = 15 * time.Minute
)

// DeviceUnderTest is a serialized cached inventory.DeviceUnderTest
type DeviceUnderTest struct {
	// Data is a serialized inventory.DeviceUnderTest.
	Data []byte
	// Updated is the last time Data was refreshed from the source-of-truth.
	Updated time.Time
}

// UpdateDUTs updates the datastore cache of DUT inventory.
func UpdateDUTs(ctx context.Context, duts []*inventory.DeviceUnderTest) error {
	now := time.Now().UTC()
	es := make([]*dutEntity, 0, len(duts))
	for _, d := range duts {
		data, err := proto.Marshal(d)
		if err != nil {
			return errors.Annotate(err, "update dut with ID %s", d.GetCommon().GetId()).Err()
		}
		es = append(es, &dutEntity{
			ID:       d.GetCommon().GetId(),
			Hostname: d.GetCommon().GetHostname(),
			Updated:  now,
			Data:     data,
		})
	}
	if err := datastore.Put(ctx, es); err != nil {
		return errors.Annotate(err, "update duts").Err()
	}
	return nil
}

// GetSerializedDUTByID gets the cached, serialized, inventory.DeviceUnderTest for a DUT.
func GetSerializedDUTByID(ctx context.Context, id string) (dut *DeviceUnderTest, rerr error) {
	defer func() {
		if rerr != nil {
			rerr = errors.Annotate(rerr, "get dut with ID %s", id).Err()
		}
	}()

	e := &dutEntity{ID: id}
	if err := datastore.Get(ctx, e); err != nil {
		return nil, err
	}
	return getDUT(ctx, e)
}

// GetSerializedDUTByHostname gets the cached, serialized inventory.DeviceUnderTest for a DUT.
func GetSerializedDUTByHostname(ctx context.Context, hostname string) (data *DeviceUnderTest, rerr error) {
	defer func() {
		if rerr != nil {
			rerr = errors.Annotate(rerr, "get dut with hostname %s", hostname).Err()
		}
	}()

	q := datastore.NewQuery(cachedInventoryDutKind)
	q = q.Eq("Hostname", hostname)

	var es []*dutEntity
	if err := datastore.GetAll(ctx, q, &es); err != nil {
		return nil, err
	}

	// Datastore can return entities that don't have the correct Hostname due to
	// asynchronous index update. Filter out these entities. This means that we
	// will temporarily return a NotFound error even though a DUT with a given
	// hostname exists.
	es = filterDUTEntitiesByHostname(es, hostname)
	switch len(es) {
	case 0:
		return nil, datastore.ErrNoSuchEntity
	case 1:
		return getDUT(ctx, es[0])
	default:
		// Found more than 1 entity for the given hostname. This can happen when a
		// DUT is swapped for a given hostname. The old DUT hasn't yet been removed
		// from the cache, but the new one has been added. In this case, we return
		// the DUT in the entity that was refreshed last.
		return getDUT(ctx, getLatestDUTEntity(es))
	}
}

func filterDUTEntitiesByHostname(es []*dutEntity, hostname string) []*dutEntity {
	r := make([]*dutEntity, 0, len(es))
	for _, e := range es {
		if e.Hostname == hostname {
			r = append(r, e)
		}
	}
	return r
}

func getLatestDUTEntity(es []*dutEntity) *dutEntity {
	if len(es) == 0 {
		panic("getLatestDUTEntity called with no entities")
	}
	r := es[0]
	for _, e := range es {
		if e.Updated.After(r.Updated) {
			r = e
		}
	}
	return r
}

func getDUT(ctx context.Context, e *dutEntity) (*DeviceUnderTest, error) {
	if isEntityStale(ctx, e) {
		logging.Infof(ctx, "Found stale dutEntity with ID %s. Warning.", e.ID)
	}
	return &DeviceUnderTest{
		Data:    e.Data,
		Updated: e.Updated,
	}, nil
}

func isEntityStale(ctx context.Context, e *dutEntity) bool {
	validity := google.DurationFromProto(config.Get(ctx).GetInventory().GetDutInfoCacheValidity())
	now := time.Now().UTC()
	return now.Sub(e.Updated) > validity
}

type dutEntity struct {
	_kind      string         `gae:"$kind,cachedInventoryDut"`
	Collection *datastore.Key `gae:"$parent"`
	ID         string         `gae:"$id"`
	Hostname   string
	Updated    time.Time
	// Data is a serialized inventory.DeviceUnderTest.
	Data []byte `gae:",noindex"`
}
