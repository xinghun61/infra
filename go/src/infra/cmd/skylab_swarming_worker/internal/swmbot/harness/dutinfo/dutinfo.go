// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package dutinfo implement loading Skylab DUT inventory info for the
// worker.
package dutinfo

import (
	"context"
	"log"
	"time"

	"github.com/golang/protobuf/proto"
	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/retry"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab_swarming_worker/internal/swmbot"
	"infra/libs/skylab/inventory"
)

// Store holds a DUT's inventory info and adds a Close method.
type Store struct {
	DUT        *inventory.DeviceUnderTest
	oldLabels  *inventory.SchedulableLabels
	updateFunc UpdateFunc
}

// Close updates the DUT's inventory info.  This method does nothing on
// subsequent calls.  This method is safe to call on a nil pointer.
func (s *Store) Close() error {
	if s == nil {
		return nil
	}
	if s.updateFunc == nil {
		return nil
	}
	c := s.DUT.GetCommon()
	new := c.GetLabels()
	inventory.SortLabels(new)
	old := s.oldLabels
	inventory.SortLabels(old)
	if new.GetUselessSwitch() {
		*new.UselessSwitch = false
	}
	if proto.Equal(new, old) {
		log.Printf("Skipping label update since there are no changes")
		return nil
	}
	log.Printf("Labels changed from %s to %s", old.String(), new.String())
	log.Printf("Calling label update function")
	if err := s.updateFunc(c.GetId(), old, new); err != nil {
		return errors.Annotate(err, "close DUT inventory").Err()
	}
	s.updateFunc = nil
	return nil
}

// UpdateFunc is used to implement inventory updating for any changes
// to the loaded DUT info.
type UpdateFunc func(dutID string, old *inventory.SchedulableLabels, new *inventory.SchedulableLabels) error

// LoadCached loads the bot's DUT's info from the inventory. Returned inventory
// data may be slightly stale compared to the source of truth of the inventory.
//
// This function returns a Store that should be closed to update the inventory
// with any changes to the info, using a supplied UpdateFunc.  If UpdateFunc is
// nil, the inventory is not updated.
func LoadCached(ctx context.Context, b *swmbot.Info, noCache bool, f UpdateFunc) (*Store, error) {
	return load(ctx, b, f, getCached)
}

// LoadFresh loads the bot's DUT's info from the inventory. Returned inventory
// data is guaranteed to be up-to-date with the source of truth of the
// inventory. This function may take longer than LoadCached because it needs
// to wait for the caches to be updated.
//
// This function returns a Store that should be closed to update the inventory
// with any changes to the info, using a supplied UpdateFunc.  If UpdateFunc is
// nil, the inventory is not updated.
func LoadFresh(ctx context.Context, b *swmbot.Info, noCache bool, f UpdateFunc) (*Store, error) {
	return load(ctx, b, f, getUncached)
}

type getDutInfoFunc func(context.Context, fleet.InventoryClient, *fleet.GetDutInfoRequest) (*fleet.GetDutInfoResponse, error)

func load(ctx context.Context, b *swmbot.Info, uf UpdateFunc, gf getDutInfoFunc) (*Store, error) {
	ctx, err := swmbot.WithSystemAccount(ctx)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	c, err := swmbot.InventoryClient(ctx, b)
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	resp, err := gf(ctx, c, &fleet.GetDutInfoRequest{Id: b.DUTID})
	if err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	var d inventory.DeviceUnderTest
	if err := proto.Unmarshal(resp.Spec, &d); err != nil {
		return nil, errors.Annotate(err, "load DUT host info").Err()
	}
	return &Store{
		DUT:        &d,
		oldLabels:  proto.Clone(d.GetCommon().GetLabels()).(*inventory.SchedulableLabels),
		updateFunc: uf,
	}, nil
}

// getCached obtains DUT info from the inventory service ignoring cache
// freshness.
func getCached(ctx context.Context, c fleet.InventoryClient, req *fleet.GetDutInfoRequest) (*fleet.GetDutInfoResponse, error) {
	resp, err := c.GetDutInfo(ctx, req)
	if err != nil {
		return nil, errors.Annotate(err, "get cached").Err()
	}
	return resp, nil
}

// getUncached obtains DUT info from the inventory service ensuring that
// returned info is up-to-date with the source of truth.
func getUncached(ctx context.Context, c fleet.InventoryClient, req *fleet.GetDutInfoRequest) (*fleet.GetDutInfoResponse, error) {
	var resp *fleet.GetDutInfoResponse
	start := time.Now().UTC()
	f := func() error {
		iresp, err := getCached(ctx, c, req)
		if err != nil {
			return err
		}
		if err := ensureResponseUpdatedSince(iresp, start); err != nil {
			return err
		}

		// Only update captured variables on success.
		resp = iresp
		return nil
	}

	if err := retry.Retry(ctx, cacheRefreshRetryFactory, f, retry.LogCallback(ctx, "dutinfo.getCached")); err != nil {
		return nil, errors.Annotate(err, "get uncached").Err()
	}
	return resp, nil
}

// cacheRefreshRetryFactory is a retry.Factory to configure retries to wait for
// inventory cache to be refreshed.
func cacheRefreshRetryFactory() retry.Iterator {
	// Cache is refreshed via a cron task that runs every minute or so.
	// Retry at: 10s, 30s, 70s, 2m10s, 3m10s, 4m10s, 5m10s
	return &retry.ExponentialBackoff{
		Limited: retry.Limited{
			Delay: 10 * time.Second,
			// Leave a little headroom for the last retry at 5m10s.
			MaxTotal: 5*time.Minute + 20*time.Second,
			// We enforce limit via MaxTotal
			Retries: -1,
		},
		MaxDelay: 1 * time.Minute,
	}
}

func ensureResponseUpdatedSince(r *fleet.GetDutInfoResponse, t time.Time) error {
	if r.Updated == nil {
		return errors.Reason("ensure uncached response: updated field is nil").Err()
	}
	u, err := ptypes.Timestamp(r.Updated)
	if err != nil {
		return errors.Annotate(err, "ensure uncached response").Err()
	}
	if t.After(u) {
		return errors.Reason("ensure uncached response: last update %s before start", t.Sub(u).String()).Err()
	}
	return nil
}
