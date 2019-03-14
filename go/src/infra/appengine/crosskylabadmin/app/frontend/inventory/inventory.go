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
	"time"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"go.chromium.org/luci/common/retry"
	"go.chromium.org/luci/common/retry/transient"
	"go.chromium.org/luci/grpc/grpcutil"
	"golang.org/x/net/context"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/clients"
	"infra/appengine/crosskylabadmin/app/config"
	"infra/appengine/crosskylabadmin/app/frontend/internal/gitstore"
	"infra/libs/skylab/inventory"
)

// GerritFactory is a contsructor for a GerritClient
type GerritFactory func(c context.Context, host string) (gerrit.GerritClient, error)

// GitilesFactory is a contsructor for a GerritClient
type GitilesFactory func(c context.Context, host string) (gitiles.GitilesClient, error)

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

	// TrackerServerFactory is a required factory function for creating a tracker object.
	//
	// TODO(pprabhu) Move tracker/tasker to individual sub-packages and inject
	// dependencies directly (instead of factory functions).
	TrackerFactory TrackerFactory
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

// UpdateDutLabels implements the method from fleet.InventoryServer interface.
func (is *ServerImpl) UpdateDutLabels(ctx context.Context, req *fleet.UpdateDutLabelsRequest) (resp *fleet.UpdateDutLabelsResponse, err error) {
	defer func() {
		err = grpcutil.GRPCifyAndLogErr(ctx, err)
	}()
	req2, err := unpackUpdateDutLabelsRequest(req)
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
			var err error
			resp, err = updateDutLabels(ctx, store, req2)
			return err
		},
		retry.LogCallback(ctx, "updateDutLabels"),
	)
	return resp, err
}

func unpackUpdateDutLabelsRequest(req *fleet.UpdateDutLabelsRequest) (updateDutLabelsRequest, error) {
	req2 := updateDutLabelsRequest{
		dutID:  req.GetDutId(),
		reason: req.GetReason(),
		labels: &inventory.SchedulableLabels{},
	}
	if err := proto.Unmarshal(req.GetLabels(), req2.labels); err != nil {
		return updateDutLabelsRequest{}, err
	}
	// Discard unknown labels to not break the inventory schema.
	proto.DiscardUnknown(req2.labels)
	return req2, nil
}

type updateDutLabelsRequest struct {
	dutID  string
	labels *inventory.SchedulableLabels
	reason string
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
