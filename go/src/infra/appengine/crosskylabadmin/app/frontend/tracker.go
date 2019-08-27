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
	"fmt"
	"sync"

	"github.com/golang/protobuf/ptypes/duration"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/data/strpair"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/botsummary"
	"infra/appengine/crosskylabadmin/app/frontend/internal/diagnosis"
	"infra/appengine/crosskylabadmin/app/frontend/internal/metrics/utilization"
)

// TrackerServerImpl implements the fleet.TrackerServer interface.
type TrackerServerImpl struct {
	// SwarmingFactory is an optional factory function for creating clients.
	//
	// If SwarmingFactory is nil, clients.NewSwarmingClient is used.
	SwarmingFactory SwarmingFactory
}

func (tsi *TrackerServerImpl) newSwarmingClient(c context.Context, host string) (clients.SwarmingClient, error) {
	if tsi.SwarmingFactory != nil {
		return tsi.SwarmingFactory(c, host)
	}
	return clients.NewSwarmingClient(c, host)
}

// PushBotsForAdminTasks implements the fleet.Tracker.pushBotsForAdminTasks() method.
func (tsi *TrackerServerImpl) PushBotsForAdminTasks(ctx context.Context, req *fleet.PushBotsForAdminTasksRequest) (res *fleet.PushBotsForAdminTasksResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	cfg := config.Get(ctx)
	sc, err := tsi.newSwarmingClient(ctx, cfg.Swarming.Host)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	// Schedule admin tasks to idle DUTs.
	dims := make(strpair.Map)
	dims[clients.DutOSDimensionKey] = []string{"OS_TYPE_CROS"}
	bots, err := sc.ListAliveIdleBotsInPool(ctx, cfg.Swarming.BotPool, strpair.Map{})
	if err != nil {
		return nil, errors.Annotate(err, "failed to list alive idle cros bots").Err()
	}
	logging.Infof(ctx, "successfully get %d alive idle cros bots.", len(bots))

	// Parse DUT name to schedule tasks for readability.
	repairDUTs, resetDUTs := identifyBots(ctx, bots)
	err1 := clients.PushRepairDUTs(ctx, repairDUTs)
	err2 := clients.PushResetDUTs(ctx, resetDUTs)
	if err1 != nil || err2 != nil {
		logging.Infof(ctx, "push repair duts: %v", err1)
		logging.Infof(ctx, "push reset duts: %v", err2)
		return nil, errors.New("failed to push repair or reset duts")
	}
	return &fleet.PushBotsForAdminTasksResponse{}, nil
}

// PushRepairJobsForLabstations implements the fleet.Tracker.pushLabstationsForRepair() method.
func (tsi *TrackerServerImpl) PushRepairJobsForLabstations(ctx context.Context, req *fleet.PushRepairJobsForLabstationsRequest) (res *fleet.PushRepairJobsForLabstationsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	cfg := config.Get(ctx)
	sc, err := tsi.newSwarmingClient(ctx, cfg.Swarming.Host)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	// Schedule repair jobs to idle labstations. It's for periodically checking
	// and rebooting labstations to ensure they're in good state.
	dims := make(strpair.Map)
	dims[clients.DutOSDimensionKey] = []string{"OS_TYPE_LABSTATION"}
	bots, err := sc.ListAliveIdleBotsInPool(ctx, cfg.Swarming.BotPool, dims)
	if err != nil {
		return nil, errors.Annotate(err, "failed to list alive idle labstation bots").Err()
	}
	logging.Infof(ctx, "successfully get %d alive idle labstation bots.", len(bots))

	// Parse DUT name to schedule tasks for readability.
	repairLabstations := identifyLabstationsForRepair(ctx, bots)

	err = clients.PushRepairLabstations(ctx, repairLabstations)
	if err != nil {
		logging.Infof(ctx, "push repair labstations: %v", err)
		return nil, errors.New("failed to push repair labstations")
	}
	return &fleet.PushRepairJobsForLabstationsResponse{}, nil
}

// ReportBots reports metrics of swarming bots.
func (tsi *TrackerServerImpl) ReportBots(ctx context.Context, req *fleet.ReportBotsRequest) (res *fleet.ReportBotsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	cfg := config.Get(ctx)
	sc, err := tsi.newSwarmingClient(ctx, cfg.Swarming.Host)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	bots, err := sc.ListAliveBotsInPool(ctx, cfg.Swarming.BotPool, strpair.Map{})
	utilization.ReportMetrics(ctx, flattenAndDedpulicateBots([][]*swarming.SwarmingRpcsBotInfo{bots}))
	return &fleet.ReportBotsResponse{}, nil
}

// RefreshBots implements the fleet.Tracker.RefreshBots() method.
func (tsi *TrackerServerImpl) RefreshBots(ctx context.Context, req *fleet.RefreshBotsRequest) (res *fleet.RefreshBotsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	cfg := config.Get(ctx)
	sc, err := tsi.newSwarmingClient(ctx, cfg.Swarming.Host)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain Swarming client").Err()
	}

	logging.Infof(ctx, "Getting bots from Swarming")
	bots, err := getBotsFromSwarming(ctx, sc, cfg.Swarming.BotPool, req.Selectors)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get bots from Swarming").Err()
	}
	if len(req.Selectors) == 0 {
		// This is a somewhat hacky hook for reporting DUT utilization metrics. We
		// only want to report metrics when the refreshed bots are not filtered, so
		// that the metrics correspond to the whole DUT fleet.
		// This endpoint is called regularly via AE cron without any filters, and
		// will report metrics regularly as part of that cron.
		utilization.ReportMetrics(ctx, bots)
	}

	bsm := botInfoToSummary(ctx, bots)
	logging.Infof(ctx, "Adding task info to bot summaries")
	if err = addTaskInfoToSummaries(ctx, sc, bsm); err != nil {
		return nil, errors.Annotate(err, "failed to set idle time for bots").Err()
	}
	logging.Infof(ctx, "Inserting bot summaries into datastore")
	updated, err := botsummary.Insert(ctx, bsm)
	if err != nil {
		return nil, errors.Annotate(err, "failed to insert bots").Err()
	}
	return &fleet.RefreshBotsResponse{
		DutIds: updated,
	}, nil
}

// SummarizeBots implements the fleet.Tracker.SummarizeBots() method.
func (tsi *TrackerServerImpl) SummarizeBots(ctx context.Context, req *fleet.SummarizeBotsRequest) (res *fleet.SummarizeBotsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()

	bses, err := botsummary.Get(ctx, req.Selectors)
	if err != nil {
		return nil, err
	}
	bss := make([]*fleet.BotSummary, 0, len(bses))
	for _, bse := range bses {
		bs, err := bse.Decode()
		if err != nil {
			return nil, errors.Annotate(err, "failed to unmarshal bot summary for bot with dut_id %q", bse.DutID).Err()
		}
		bss = append(bss, bs)
	}
	return &fleet.SummarizeBotsResponse{
		Bots: bss,
	}, nil
}

// getBotsFromSwarming lists bots by calling the Swarming service.
func getBotsFromSwarming(ctx context.Context, sc clients.SwarmingClient, pool string, sels []*fleet.BotSelector) ([]*swarming.SwarmingRpcsBotInfo, error) {
	// No filters implies get all bots.
	if len(sels) == 0 {
		bots, err := sc.ListAliveBotsInPool(ctx, pool, strpair.Map{})
		if err != nil {
			return nil, errors.Annotate(err, "failed to get bots in pool %s", pool).Err()
		}
		return bots, nil
	}

	bots := make([][]*swarming.SwarmingRpcsBotInfo, 0, len(sels))
	// Protects access to bots
	m := &sync.Mutex{}
	err := parallel.WorkPool(clients.MaxConcurrentSwarmingCalls, func(workC chan<- func() error) {
		for i := range sels {
			// In-scope variable for goroutine closure.
			sel := sels[i]
			workC <- func() error {
				bs, ierr := getFilteredBotsFromSwarming(ctx, sc, pool, sel)
				if ierr != nil {
					return ierr
				}
				m.Lock()
				defer m.Unlock()
				bots = append(bots, bs)
				return nil
			}
		}
	})
	return flattenAndDedpulicateBots(bots), err
}

// getFilteredBotsFromSwarming lists bots for a single selector by calling the
// Swarming service.
//
// This function is intended to be used in a parallel.WorkPool().
func getFilteredBotsFromSwarming(ctx context.Context, sc clients.SwarmingClient, pool string, sel *fleet.BotSelector) ([]*swarming.SwarmingRpcsBotInfo, error) {
	dims := make(strpair.Map)
	if id := sel.GetDutId(); id != "" {
		dims[clients.DutIDDimensionKey] = []string{id}
	}
	if m := sel.GetDimensions().GetModel(); m != "" {
		dims[clients.DutModelDimensionKey] = []string{m}
	}
	if p := sel.GetDimensions().GetPools(); len(p) > 0 {
		dims[clients.DutPoolDimensionKey] = p
	}
	if n := sel.GetDimensions().GetDutName(); n != "" {
		dims[clients.DutNameDimensionKey] = []string{n}
	}

	if len(dims) == 0 {
		return nil, fmt.Errorf("empty selector %v", sel)
	}
	bs, err := sc.ListAliveBotsInPool(ctx, pool, dims)
	if err != nil {
		return nil, errors.Annotate(err, "failed to get bots in pool %s with dimensions %s", pool, dims).Err()
	}
	return bs, nil
}

func flattenAndDedpulicateBots(nb [][]*swarming.SwarmingRpcsBotInfo) []*swarming.SwarmingRpcsBotInfo {
	bm := make(map[string]*swarming.SwarmingRpcsBotInfo)
	for _, bs := range nb {
		for _, b := range bs {
			bm[b.BotId] = b
		}
	}
	bots := make([]*swarming.SwarmingRpcsBotInfo, 0, len(bm))
	for _, v := range bm {
		bots = append(bots, v)
	}
	return bots
}

var healthyDutStates = map[fleet.DutState]bool{
	fleet.DutState_Ready:        true,
	fleet.DutState_NeedsCleanup: true,
	fleet.DutState_NeedsRepair:  true,
	fleet.DutState_NeedsReset:   true,
}

// botInfoToSummary initializes fleet.BotSummary for each bot.
//
// This function returns a map from the bot ID to fleet.BotSummary object for
// it.
func botInfoToSummary(ctx context.Context, bots []*swarming.SwarmingRpcsBotInfo) map[string]*fleet.BotSummary {
	bsm := make(map[string]*fleet.BotSummary, len(bots))
	for _, bi := range bots {
		bs, err := singleBotInfoToSummary(bi)
		if err != nil {
			logging.Errorf(ctx, "failed to make summary for bot %s: %s", bi.BotId, err)
			continue
		}
		bsm[bi.BotId] = bs
	}
	return bsm
}

// singleBotInfoToSummary returns a BotSummary for the bot.
func singleBotInfoToSummary(bi *swarming.SwarmingRpcsBotInfo) (*fleet.BotSummary, error) {
	bs := &fleet.BotSummary{
		Dimensions: &fleet.BotDimensions{},
	}
	dims := swarmingDimensionsMap(bi.Dimensions)
	var err error
	bs.DutId, err = extractSingleValuedDimension(dims, clients.DutIDDimensionKey)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain DUT ID for bot %q", bi.BotId).Err()
	}
	bs.Dimensions.DutName, err = extractSingleValuedDimension(dims, clients.DutNameDimensionKey)
	if err != nil {
		return nil, errors.Annotate(err, "failed to obtain DUT name for bot %q", bi.BotId).Err()
	}

	bs.DutState = clients.GetStateDimension(bi.Dimensions)
	if bs.DutState == fleet.DutState_DutStateInvalid {
		return nil, errors.Reason("failed to obtain DutState for bot %q", bi.BotId).Err()
	}

	if vs := dims[clients.DutModelDimensionKey]; len(vs) == 1 {
		bs.Dimensions.Model = vs[0]
	}
	bs.Dimensions.Pools = dims[clients.DutPoolDimensionKey]
	if healthy := healthyDutStates[bs.DutState]; healthy {
		bs.Health = fleet.Health_Healthy
	} else {
		bs.Health = fleet.Health_Unhealthy
	}
	return bs, nil
}

// addTaskInfoToSummaries updates the bot summaries with information
// derived from the bot's tasks.
func addTaskInfoToSummaries(ctx context.Context, sc clients.SwarmingClient, bsm map[string]*fleet.BotSummary) error {
	return parallel.WorkPool(clients.MaxConcurrentSwarmingCalls, func(workC chan<- func() error) {
		for bid := range bsm {
			// In-scope variable for goroutine closure.
			bid := bid
			bs := bsm[bid]
			workC <- func() error {
				return addTaskInfoToSummary(ctx, sc, bid, bs)
			}
		}
	})
}

// addTaskInfoToSummary updates the bot summary with information derived
// from the bot's tasks.
func addTaskInfoToSummary(ctx context.Context, sc clients.SwarmingClient, botID string, bs *fleet.BotSummary) error {
	d, err := getIdleDuration(ctx, sc, botID)
	if err != nil {
		return errors.Annotate(err, "failed to get idle duration of bot %s", botID).Err()
	}
	bs.IdleDuration = d
	ts, err := diagnosis.Diagnose(ctx, sc, botID, bs.DutState)
	if err != nil {
		return errors.Annotate(err, "failed to get diagnosis for bot %s", botID).Err()
	}
	bs.Diagnosis = ts
	return nil
}

// getIdleDuration queries swarming for the duration since last task on the
// bot.
func getIdleDuration(ctx context.Context, sc clients.SwarmingClient, botID string) (*duration.Duration, error) {
	trs, err := sc.ListSortedRecentTasksForBot(ctx, botID, 1)
	if err != nil {
		return nil, errors.Annotate(err, "failed to list recent tasks for bot %s", botID).Err()
	}
	if len(trs) == 0 {
		return nil, nil
	}
	tr := trs[0]
	d, err := clients.TimeSinceBotTask(tr)
	if err != nil {
		return nil, errors.Annotate(err, "failed to determine time since task %s", tr.TaskId).Err()
	}
	return d, nil
}

func swarmingDimensionsMap(sdims []*swarming.SwarmingRpcsStringListPair) strpair.Map {
	dims := make(strpair.Map)
	for _, sdim := range sdims {
		dims[sdim.Key] = sdim.Value
	}
	return dims
}

func extractSingleValuedDimension(dims strpair.Map, key string) (string, error) {
	vs, ok := dims[key]
	if !ok {
		return "", fmt.Errorf("failed to find dimension %s", key)
	}
	switch len(vs) {
	case 1:
		return vs[0], nil
	case 0:
		return "", fmt.Errorf("no value for dimension %s", key)
	default:
		return "", fmt.Errorf("multiple values for dimension %s", key)
	}
}

// identifyBots identifies bots that need reset and need repair.
func identifyBots(ctx context.Context, bots []*swarming.SwarmingRpcsBotInfo) (repairDUTs []string, resetDUTs []string) {
	repairDUTs = make([]string, 0, len(bots))
	resetDUTs = make([]string, 0, len(bots))
	for _, b := range bots {
		s := clients.GetStateDimension(b.Dimensions)
		dims := swarmingDimensionsMap(b.Dimensions)
		os, err := extractSingleValuedDimension(dims, clients.DutOSDimensionKey)
		n, err := extractSingleValuedDimension(dims, clients.DutNameDimensionKey)
		if err != nil {
			logging.Warningf(ctx, "failed to obtain DUT name for bot %q", b.BotId)
			continue
		}
		if os == "OS_TYPE_CROS" && (s == fleet.DutState_NeedsRepair || s == fleet.DutState_RepairFailed) {
			repairDUTs = append(repairDUTs, n)
		}
		if os == "OS_TYPE_CROS" && s == fleet.DutState_NeedsReset {
			resetDUTs = append(resetDUTs, n)
		}
	}
	return repairDUTs, resetDUTs
}

// identifyLabstationsForRepair identifies labstations that need repair.
func identifyLabstationsForRepair(ctx context.Context, bots []*swarming.SwarmingRpcsBotInfo) (repairLabstations []string) {
	dutNames := make([]string, 0, len(bots))
	for _, b := range bots {
		dims := swarmingDimensionsMap(b.Dimensions)
		os, err := extractSingleValuedDimension(dims, clients.DutOSDimensionKey)
		n, err := extractSingleValuedDimension(dims, clients.DutNameDimensionKey)
		if err != nil {
			logging.Warningf(ctx, "failed to obtain DUT name for bot %q", b.BotId)
			continue
		}
		if os == "OS_TYPE_LABSTATION" {
			dutNames = append(dutNames, n)
		}
	}
	return dutNames
}
