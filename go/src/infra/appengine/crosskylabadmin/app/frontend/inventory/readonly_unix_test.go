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

// +build !windows

// TODO(crbug.com/939418): These tests flake specifically on Windows
// for an unknown reason.

package inventory

import (
	"testing"
	"time"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/appengine/crosskylabadmin/app/frontend/internal/fakes"

	"go.chromium.org/luci/common/proto/gerrit"
	"go.chromium.org/luci/common/proto/gitiles"
	"golang.org/x/net/context"
)

func TestGetDutInfoAfterUpdating(t *testing.T) {
	t.Parallel()
	ctx := testingContext()
	ctx = withDutInfoCacheValidity(ctx, 100*time.Minute)

	gc := fakes.NewGitilesClient()
	inv := fakeServer()
	inv.GitilesFactory = func(context.Context, string) (gitiles.GitilesClient, error) {
		return gc, nil
	}
	setGitilesDUTs(ctx, gc, []testInventoryDut{
		{id: "dut1_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
	})
	_, err := inv.UpdateCachedInventory(ctx, &fleet.UpdateCachedInventoryRequest{})
	if err != nil {
		t.Fatalf("UpdateCachedInventory returned non-nil error: %s", err)
	}
	setGitilesDUTs(ctx, gc, []testInventoryDut{
		{id: "dut1_new_id", hostname: "dut1_hostname", model: "link", pool: "DUT_POOL_SUITES"},
	})
	_, err = inv.UpdateCachedInventory(ctx, &fleet.UpdateCachedInventoryRequest{})
	if err != nil {
		t.Fatalf("UpdateCachedInventory returned non-nil error: %s", err)
	}

	resp, err := inv.GetDutInfo(ctx, &fleet.GetDutInfoRequest{Hostname: "dut1_hostname"})
	if err != nil {
		t.Fatalf("GetDutInfo returned non-nil error: %s", err)
	}
	dut := getDutInfoBasic(t, resp)
	if id := dut.GetCommon().GetId(); id != "dut1_new_id" {
		t.Errorf("Got DUT ID %s; want dut1_new_id", id)
	}
	if hostname := dut.GetCommon().GetHostname(); hostname != "dut1_hostname" {
		t.Errorf("Got DUT hostname %s; want dut1_hostname", hostname)
	}
}

func fakeServer() *ServerImpl {
	return &ServerImpl{
		GerritFactory:  gerritFactory,
		GitilesFactory: gitilesFactory,
	}
}

func gerritFactory(context.Context, string) (gerrit.GerritClient, error) {
	return &fakes.GerritClient{}, nil
}

func gitilesFactory(context.Context, string) (gitiles.GitilesClient, error) {
	return fakes.NewGitilesClient(), nil
}
