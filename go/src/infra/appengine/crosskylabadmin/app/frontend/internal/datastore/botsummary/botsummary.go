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

// Package botsummary implements datastore bot summary access.
package botsummary

import (
	"context"
	"fmt"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	"go.chromium.org/luci/common/errors"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

// botSummaryKind is the datastore entity kind for fleetBotSummaryEntity.
const botSummaryKind = "fleetBotSummary"

// Entity is a datastore entity that stores fleet.BotSummary in
// protobuf binary format.
//
// In effect, this is a cache of task and bot history information
// from the Swarming server over a fixed time period.
type Entity struct {
	_kind string `gae:"$kind,fleetBotSummary"`
	// Swarming bot's dut_id dimension.
	//
	// This dimension is an opaque reference to the managed DUT's uuid in skylab
	// inventory data.
	DutID string `gae:"$id"`
	// BotID is the unique ID of the swarming bot.
	BotID string
	// Data is the fleet.BotSummary object serialized to protobuf binary format.
	Data []byte `gae:",noindex"`
}

// Decode converts the Entity into a fleet.BotSummary.
func (e *Entity) Decode() (*fleet.BotSummary, error) {
	var bs fleet.BotSummary
	if err := proto.Unmarshal(e.Data, &bs); err != nil {
		return nil, errors.Annotate(err, "failed to unmarshal bot summary for bot with dut_id %q", e.DutID).Err()
	}
	return &bs, nil
}

// Insert inserts fleet.BotSummary into datastore.
func Insert(ctx context.Context, bsm map[string]*fleet.BotSummary) (dutIDs []string, err error) {
	updated := make([]string, 0, len(bsm))
	es := make([]*Entity, 0, len(bsm))
	for bid, bs := range bsm {
		data, err := proto.Marshal(bs)
		if err != nil {
			return nil, errors.Annotate(err, "failed to marshal BotSummary for dut %q", bs.DutId).Err()
		}
		es = append(es, &Entity{
			DutID: bs.DutId,
			BotID: bid,
			Data:  data,
		})
		updated = append(updated, bs.DutId)
	}
	if err := datastore.Put(ctx, es); err != nil {
		return nil, errors.Annotate(err, "failed to put BotSummaries").Err()
	}
	return updated, nil
}

// Get gets Entites from datastore.
func Get(ctx context.Context, sels []*fleet.BotSelector) ([]*Entity, error) {
	// No selectors implies summarize all bots.
	if len(sels) == 0 {
		es := []*Entity{}
		q := datastore.NewQuery(botSummaryKind)
		err := datastore.GetAll(ctx, q, &es)
		if err != nil {
			return nil, errors.Annotate(err, "failed to get all bots from datastore").Err()
		}
		return es, nil
	}

	// For now, each selector can only yield 0 or 1 BotSummary.
	es := make([]*Entity, 0, len(sels))
	for _, s := range sels {
		// datastore rejects search for empty key with InvalidKey.
		// For us, this is simply an impossible filter.
		if s.DutId == "" {
			continue
		}

		es = append(es, &Entity{
			DutID: s.DutId,
		})
	}

	if err := datastore.Get(ctx, es); err != nil {
		switch err := err.(type) {
		case errors.MultiError:
			return filterNotFoundEntities(es, err)
		default:
			return nil, err
		}
	}
	return es, nil
}

func filterNotFoundEntities(es []*Entity, merr errors.MultiError) ([]*Entity, error) {
	if len(es) != len(merr) {
		panic(fmt.Sprintf("Length of bot summary (%d) does not match length of multierror (%d)", len(es), len(merr)))
	}
	filtered := make([]*Entity, 0, len(es))
	errs := make(errors.MultiError, 0, len(merr))
	for i, e := range es {
		err := merr[i]
		if err != nil {
			if !datastore.IsErrNoSuchEntity(err) {
				errs = append(errs, err)
			}
			continue
		}
		filtered = append(filtered, e)
	}
	if errs.First() != nil {
		return nil, errs
	}
	return filtered, nil
}
