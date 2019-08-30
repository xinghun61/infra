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

// Package inventory implements the fleet.Inventory service end-points of
// corsskylabadmin.
package inventory

import (
	"fmt"
	"sync"
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/chromiumos/infra/proto/go/device"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/grpc/grpcutil"
	"go.chromium.org/luci/grpc/prpc"
	"go.chromium.org/luci/server/auth"
	"golang.org/x/net/context"
	"golang.org/x/oauth2"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/datastore/dronecfg"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/appengine/drone-queen/api"
	"infra/libs/skylab/inventory"
)

// GerritFactory is a contsructor for a GerritClient
type GerritFactory func(c context.Context, host string) (gerrit.GerritClient, error)

// GitilesFactory is a contsructor for a GerritClient
type GitilesFactory func(c context.Context, host string) (gitiles.GitilesClient, error)

// SwarmingFactory is a constructor for a SwarmingClient.
type SwarmingFactory func(c context.Context, host string) (clients.SwarmingClient, error)

// TrackerFactory is a constructor for a TrackerServer object.
type TrackerFactory func() fleet.TrackerServer

// ServerImpl implements the fleet.InventoryServer interface.
type ServerImpl struct {
	// GerritFactory is an optional factory function for creating gerrit client.
	//
	// If GerritFactory is nil, clients.NewGerritClient is used.
	GerritFactory GerritFactory

	// GitilesFactory is an optional factory function for creating gitiles client.
	//
	// If GitilesFactory is nil, clients.NewGitilesClient is used.
	GitilesFactory GitilesFactory

	// SwarmingFactory is an optional factory function for creating clients.
	//
	// If SwarmingFactory is nil, clients.NewSwarmingClient is used.
	SwarmingFactory SwarmingFactory

	// TrackerServerFactory is a required factory function for creating a tracker object.
	//
	// TODO(pprabhu) Move tracker/tasker to individual sub-packages and inject
	// dependencies directly (instead of factory functions).
	TrackerFactory TrackerFactory

	// updateLimiter rate limits UpdateDutLabels.
	updateLimiter     rateLimiter
	updateLimiterOnce sync.Once
}

var transientErrorRetriesTemplate = retry.ExponentialBackoff{
	Limited: retry.Limited{
		Delay: 200 * time.Millisecond,
		// Don't retry too often, leaving some headroom for clients to retry if they wish.
		Retries: 3,
	},
	// Slow down quickly so as to not flood outbound requests on retries.
	Multiplier: 4,
	MaxDelay:   5 * time.Second,
}

// transientErrorRetries returns a retry.Factory to use on transient errors on
// outbound requests.
func transientErrorRetries() retry.Factory {
	next := func() retry.Iterator {
		it := transientErrorRetriesTemplate
		return &it
	}
	return transient.Only(next)
}

func (is *ServerImpl) newGerritClient(c context.Context, host string) (gerrit.GerritClient, error) {
	if is.GerritFactory != nil {
		return is.GerritFactory(c, host)
	}
	return clients.NewGerritClient(c, host)
}

func (is *ServerImpl) newGitilesClient(c context.Context, host string) (gitiles.GitilesClient, error) {
	if is.GitilesFactory != nil {
		return is.GitilesFactory(c, host)
	}
	return clients.NewGitilesClient(c, host)
}

func (is *ServerImpl) newSwarmingClient(ctx context.Context, host string) (clients.SwarmingClient, error) {
	if is.SwarmingFactory != nil {
		return is.SwarmingFactory(ctx, host)
	}
	return clients.NewSwarmingClient(ctx, host)
}

func (is *ServerImpl) newStore(ctx context.Context) (*gitstore.InventoryStore, error) {
	inventoryConfig := config.Get(ctx).Inventory
	gerritC, err := is.newGerritClient(ctx, inventoryConfig.GerritHost)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory store").Err()
	}
	gitilesC, err := is.newGitilesClient(ctx, inventoryConfig.GitilesHost)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory store").Err()
	}
	return gitstore.NewInventoryStore(gerritC, gitilesC), nil
}

// UpdateDeviceConfig implements updating device config to inventory.
func (is *ServerImpl) UpdateDeviceConfig(ctx context.Context, req *fleet.UpdateDeviceConfigRequest) (resp *fleet.UpdateDeviceConfigResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	cfg := config.Get(ctx).Inventory
	gitilesC, err := is.newGitilesClient(ctx, cfg.GitilesHost)
	if err != nil {
		return nil, errors.Annotate(err, "fail to update device config").Err()
	}
	deviceConfigs, err := GetDeviceConfig(ctx, gitilesC)
	if err != nil {
		return nil, errors.Annotate(err, "fail to fetch device configs").Err()
	}
	err = SaveDeviceConfig(ctx, deviceConfigs)
	if err != nil {
		return nil, errors.Annotate(err, "fail to save device config to datastore").Err()
	}
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	if err := store.Refresh(ctx); err != nil {
		return nil, errors.Annotate(err, "fail to refresh inventory store").Err()
	}
	url, err := updateDeviceConfig(ctx, deviceConfigs, store)
	if err != nil {
		return nil, err
	}
	logging.Infof(ctx, "successfully update device config: %s", url)

	return &fleet.UpdateDeviceConfigResponse{}, nil
}

func updateDeviceConfig(ctx context.Context, deviceConfigs map[string]*device.Config, s *gitstore.InventoryStore) (string, error) {
	for _, d := range s.Lab.GetDuts() {
		c := d.GetCommon()
		dcID := getIDForInventoryLabels(ctx, c.GetLabels())
		standardDC, ok := deviceConfigs[dcID]
		if !ok {
			continue
		}
		inventory.ConvertDeviceConfig(standardDC, c)
	}
	url, err := s.Commit(ctx, fmt.Sprintf("Update device config"))
	if gitstore.IsEmptyErr(err) {
		return "no commit for empty diff", nil
	}
	if err != nil {
		return "", errors.Annotate(err, "fail to update device config").Err()
	}
	return url, nil
}

// UpdateDutLabels implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) UpdateDutLabels(ctx context.Context, req *fleet.UpdateDutLabelsRequest) (resp *fleet.UpdateDutLabelsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	req2, err := unpackUpdateDutLabelsRequest(req)
	if UpdateDCAndCheckIfSkipLabelUpdate(ctx, req2) {
		logging.Infof(ctx, "skip label update if there's no difference except device config between old and new labels")
		return &fleet.UpdateDutLabelsResponse{}, nil
	}
	is.initUpdateLimiterOnce(ctx)
	if !is.updateLimiter.TryRequest() {
		return nil, status.Error(codes.Unavailable, "update is rate limited")
	}
	if err != nil {
		return nil, err
	}
	store, err := is.newStore(ctx)
	if err != nil {
		return nil, err
	}
	err = retry.Retry(
		ctx,
		transientErrorRetries(),
		func() error {
			var err2 error
			resp, err2 = updateDutLabels(ctx, store, req2)
			return err2
		},
		retry.LogCallback(ctx, "updateDutLabels"),
	)
	return resp, err
}

// PushInventoryToQueen implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) PushInventoryToQueen(ctx context.Context, req *fleet.PushInventoryToQueenRequest) (resp *fleet.PushInventoryToQueenResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	cfg := config.Get(ctx).Inventory
	if cfg.QueenService == "" {
		return &fleet.PushInventoryToQueenResponse{}, nil
	}
	e, err := dronecfg.Get(ctx, queenDroneName(cfg.Environment))
	if err != nil {
		return nil, err
	}
	duts := make([]string, len(e.DUTs))
	for i, d := range e.DUTs {
		duts[i] = d.Hostname
	}

	ts, err := auth.GetTokenSource(ctx, auth.AsSelf)
	if err != nil {
		return nil, err
	}
	h := oauth2.NewClient(ctx, ts)
	c := api.NewInventoryProviderPRPCClient(&prpc.Client{
		C:    h,
		Host: cfg.QueenService,
	})
	_, err = c.DeclareDuts(ctx, &api.DeclareDutsRequest{Duts: duts})
	if err != nil {
		return nil, err
	}
	return &fleet.PushInventoryToQueenResponse{}, nil
}

// queenDroneName returns the name of the fake drone whose DUTs should
// be pushed to the drone queen service.
func queenDroneName(env string) string {
	return queenDronePrefix + env
}

const queenDronePrefix = "drone-queen-"

// UpdateDCAndCheckIfSkipLabelUpdate updates DUT labels with cached device config and checks if skipping DUT label update.
func UpdateDCAndCheckIfSkipLabelUpdate(ctx context.Context, req updateDutLabelsRequest) bool {
	logging.Infof(ctx, "labels before update: %s", req.oldLabels.String())
	logging.Infof(ctx, "labels after update: %s", req.labels.String())
	if req.oldLabels.String() == "" {
		logging.Warningf(ctx, "old labels hasn't been set, won't skip update")
		return false
	}
	if getIDForInventoryLabels(ctx, req.labels) != getIDForInventoryLabels(ctx, req.oldLabels) {
		logging.Warningf(ctx, "inconsistent device config ID, won't skip update")
		return false
	}
	if err := UpdateLabelsWithDeviceConfig(ctx, req.labels); err != nil {
		logging.Warningf(ctx, "fail to sync device config for new labels %s", req.labels.String())
	}
	if err := UpdateLabelsWithDeviceConfig(ctx, req.oldLabels); err != nil {
		logging.Warningf(ctx, "fail to sync device config for old labels %s", req.oldLabels.String())
	}
	if proto.Equal(req.oldLabels, req.labels) {
		logging.Infof(ctx, "no difference between old and new labels except device config")
		return true
	}
	logging.Infof(ctx, "device config differ between old and new labels, won't skip update")
	return false
}

// initUpdateLimiterOnce initializes the updateLimiter.  This should
// be called before using updateLimiter always.
func (is *ServerImpl) initUpdateLimiterOnce(ctx context.Context) {
	is.updateLimiterOnce.Do(func() {
		is.updateLimiter.limitPerPeriod = int(config.Get(ctx).Inventory.UpdateLimitPerMinute)
		is.updateLimiter.period = time.Minute
	})
}

func unpackUpdateDutLabelsRequest(req *fleet.UpdateDutLabelsRequest) (updateDutLabelsRequest, error) {
	req2 := updateDutLabelsRequest{
		dutID:     req.GetDutId(),
		reason:    req.GetReason(),
		labels:    &inventory.SchedulableLabels{},
		oldLabels: &inventory.SchedulableLabels{},
	}
	if err := proto.Unmarshal(req.GetLabels(), req2.labels); err != nil {
		return updateDutLabelsRequest{}, err
	}
	if err := proto.Unmarshal(req.GetOldLabels(), req2.oldLabels); err != nil {
		return updateDutLabelsRequest{}, err
	}
	// Discard unknown labels to not break the inventory schema.
	proto.DiscardUnknown(req2.labels)
	proto.DiscardUnknown(req2.oldLabels)
	return req2, nil
}

type updateDutLabelsRequest struct {
	dutID     string
	labels    *inventory.SchedulableLabels
	reason    string
	oldLabels *inventory.SchedulableLabels
}

func updateDutLabels(ctx context.Context, s *gitstore.InventoryStore, req updateDutLabelsRequest) (*fleet.UpdateDutLabelsResponse, error) {
	var resp fleet.UpdateDutLabelsResponse
	if err := s.Refresh(ctx); err != nil {
		return nil, errors.Annotate(err, "updateDutLabels").Err()
	}

	dut, ok := getDUTByID(s.Lab, req.dutID)
	if !ok {
		return nil, errors.Reason("updateDutLabels: no DUT found").Err()
	}
	c := dut.GetCommon()
	// Repair should not change pool labels.
	req.labels.CriticalPools = c.Labels.CriticalPools
	req.labels.SelfServePools = c.Labels.SelfServePools
	c.Labels = req.labels
	url, err := s.Commit(ctx, fmt.Sprintf("Update DUT labels for %s", req.reason))
	if gitstore.IsEmptyErr(err) {
		return &resp, nil
	}
	if err != nil {
		return nil, errors.Annotate(err, "updateDutLabels").Err()
	}
	resp.Url = url

	return &resp, nil
}

func getDUTByID(lab *inventory.Lab, id string) (*inventory.DeviceUnderTest, bool) {
	for _, d := range lab.GetDuts() {
		if d.GetCommon().GetId() == id {
			return d, true
		}
	}
	return nil, false
}

func mapHostnameToDUTs(duts []*inventory.DeviceUnderTest) map[string]*inventory.DeviceUnderTest {
	m := make(map[string]*inventory.DeviceUnderTest)
	for _, d := range duts {
		m[d.GetCommon().GetHostname()] = d
	}
	return m
}
