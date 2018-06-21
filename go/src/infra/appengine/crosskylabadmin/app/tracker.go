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

package app

import (
	"fmt"
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/gae/service/datastore"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/sync/parallel"
	"golang.org/x/net/context"
)

// trackerServerImpl implements the fleet.TrakerServer interface.
type trackerServerImpl struct {
	swarmingClientFactory
}

const (
	dutIDDimensionKey          = "dut_id"
	maxConcurrentSwarmingCalls = 10
)

// RefreshBots implements the fleet.Tracker.RefreshBots() method.
func (tsi *trackerServerImpl) RefreshBots(c context.Context, req *fleet.RefreshBotsRequest) (res *fleet.RefreshBotsResponse, err error) {
	defer func() {
		err = grpcfyRawErrors(err)
	}()

	sc, err := tsi.swarmingClient(c, swarmingInstance)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	bots, err := getBotsFromSwarming(c, sc, req.Selectors)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get bots from Swarming").Err()
	}
	updated, err := insertBotSummary(c, bots)
	if err != nil {
		return nil, errors.Annotate(err, "failed to insert bots").Err()
	}
	return &fleet.RefreshBotsResponse{
		DutIds: updated,
	}, nil
}

// SummarizeBots implements the fleet.Tracker.SummarizeBots() method.
func (tsi *trackerServerImpl) SummarizeBots(c context.Context, req *fleet.SummarizeBotsRequest) (res *fleet.SummarizeBotsResponse, err error) {
	defer func() {
		err = grpcfyRawErrors(err)
	}()

	bses, err := getBotSummariesFromDatastore(c, req.Selectors)
	if err != nil {
		return nil, err
	}
	bss := make([]*fleet.BotSummary, 0, len(bses))
	for _, bse := range bses {
		bs := &fleet.BotSummary{}
		if err := proto.Unmarshal(bse.Data, bs); err != nil {
			return nil, errors.Annotate(err, "failed to unmarshal bot summary for bot with dut_id %q", bse.DutID).Err()
		}
		bss = append(bss, bs)
	}
	return &fleet.SummarizeBotsResponse{
		Bots: bss,
	}, nil
}

// getBotsFromSwarming lists bots by calling the Swarming service.
func getBotsFromSwarming(c context.Context, sc SwarmingClient, sels []*fleet.BotSelector) ([]*swarming.SwarmingRpcsBotInfo, error) {
	// No filters implies get all bots.
	if len(sels) == 0 {
		bots, err := sc.ListAliveBotsInPool(c, swarmingBotPool, strpair.Map{})
		if err != nil {
			return nil, errors.Annotate(err, "failed to get bots in pool %s", swarmingBotPool).Err()
		}
		return bots, nil
	}

	// Closed by the master goroutine when all bots have been listed.
	botsC := make(chan *swarming.SwarmingRpcsBotInfo, 1)
	errC := make(chan error, 1)
	defer close(errC)
	go func() {
		// This goroutine is referred to as the "master goroutine".
		defer close(botsC)
		sels = dropDuplicateSelectors(sels)
		errC <- parallel.WorkPool(maxConcurrentSwarmingCalls, func(workC chan<- func() error) {
			for i := range sels {
				// In-scope variable for goroutine closure.
				sel := sels[i]
				f := func() error {
					return getFilteredBotsFromSwarming(c, sc, sel, botsC)
				}
				select {
				case <-c.Done():
					return
				case workC <- f:
					continue
				}
			}
		})
	}()

	// For now, each selector can only yield 0 or 1 bot to update.
	bots := make([]*swarming.SwarmingRpcsBotInfo, 0, len(sels))
	for b := range botsC {
		bots = append(bots, b)
	}
	select {
	case err := <-errC:
		return bots, err
	default:
		// WorkPool may terminate silently due to c.Done().
		return bots, c.Err()
	}
}

// getFilteredBotsFromSwarming lists bots for a single selector by calling the Swarming service.
// This function is intended to be used in a parallel.WorkPool().
func getFilteredBotsFromSwarming(c context.Context, sc SwarmingClient, sel *fleet.BotSelector, botsC chan *swarming.SwarmingRpcsBotInfo) error {
	dims := strpair.Map{
		dutIDDimensionKey: []string{sel.DutId},
	}
	bs, err := sc.ListAliveBotsInPool(c, swarmingBotPool, dims)
	if err != nil {
		return errors.Annotate(err, "failed to get bots in pool %s with dimensions %s", swarmingBotPool, dims).Err()
	}
	for _, b := range bs {
		select {
		case <-c.Done():
			// Context error will be returned only once, outside of the WorkPool.
			return nil
		case botsC <- b:
			continue
		}
	}
	return nil
}

// datastore as botSummaryEntity structs.
// insertBotSummary returns the dut_ids of bots inserted.
func insertBotSummary(c context.Context, bots []*swarming.SwarmingRpcsBotInfo) ([]string, error) {
	updated := make([]string, 0, len(bots))
	bss := make([]*fleetBotSummaryEntity, 0, len(bots))
	for _, bi := range bots {
		dutID, err := dutIDFromBotInfo(bi)
		if err != nil {
			return nil, errors.Annotate(err, "failed to obtain dutID for bot %q", bi.BotId).Err()
		}
		data, err := proto.Marshal(&fleet.BotSummary{
			DutId: dutID,
		})
		if err != nil {
			return nil, errors.Annotate(err, "failed to marshal BotSummary for dut %q", dutID).Err()
		}
		bss = append(bss, &fleetBotSummaryEntity{
			DutID: dutID,
			Data:  data,
		})
		updated = append(updated, dutID)
	}
	if err := datastore.Put(c, bss); err != nil {
		return nil, errors.Annotate(err, "failed to put BotSummaries").Err()
	}
	return updated, nil
}

func dutIDFromBotInfo(bi *swarming.SwarmingRpcsBotInfo) (string, error) {
	for _, dim := range bi.Dimensions {
		if dim.Key == dutIDDimensionKey {
			switch len(dim.Value) {
			case 1:
				return dim.Value[0], nil
			case 0:
				return "", fmt.Errorf("no value for dimension %s", dutIDDimensionKey)
			default:
				return "", fmt.Errorf("multiple values for dimension %s", dutIDDimensionKey)
			}
		}
	}
	return "", fmt.Errorf("failed to find dimension %s", dutIDDimensionKey)
}

func getBotSummariesFromDatastore(c context.Context, sels []*fleet.BotSelector) ([]*fleetBotSummaryEntity, error) {
	// No selectors implies summarize all bots.
	if len(sels) == 0 {
		bses := []*fleetBotSummaryEntity{}
		q := datastore.NewQuery(botSummaryKind)
		err := datastore.GetAll(c, q, &bses)
		if err != nil {
			return nil, errors.Annotate(err, "failed to get all bots from datastore").Err()
		}
		return bses, nil
	}

	// For now, each selector can only yield 0 or 1 BotSummary.
	bses := make([]*fleetBotSummaryEntity, 0, len(sels))
	for _, s := range sels {
		// datastore rejects search for empty key with InvalidKey.
		// For us, this is simply an impossible filter.
		if s.DutId == "" {
			continue
		}

		bses = append(bses, &fleetBotSummaryEntity{
			DutID: s.DutId,
		})
	}

	if err := datastore.Get(c, bses); err != nil {
		switch err := err.(type) {
		case errors.MultiError:
			return filterNotFoundEntities(bses, err)
		default:
			return nil, err
		}
	}
	return bses, nil
}

func filterNotFoundEntities(bses []*fleetBotSummaryEntity, merr errors.MultiError) ([]*fleetBotSummaryEntity, error) {
	if len(bses) != len(merr) {
		panic(fmt.Sprintf("Length of bot summary (%d) does not match length of multierror (%d)", len(bses), len(merr)))
	}
	filtered := make([]*fleetBotSummaryEntity, 0, len(bses))
	errs := make(errors.MultiError, 0, len(merr))
	for i := range bses {
		err := merr[i]
		if err != nil {
			if !datastore.IsErrNoSuchEntity(err) {
				errs = append(errs, err)
			}
			continue
		}
		filtered = append(filtered, bses[i])
	}
	if errs.First() != nil {
		return nil, errs
	}
	return filtered, nil
}

func dropDuplicateSelectors(sels []*fleet.BotSelector) []*fleet.BotSelector {
	msels := make(map[string]*fleet.BotSelector, len(sels))
	for _, s := range sels {
		msels[s.DutId] = s
	}
	usels := make([]*fleet.BotSelector, 0, len(msels))
	for _, s := range msels {
		usels = append(usels, s)
	}
	return usels
}
