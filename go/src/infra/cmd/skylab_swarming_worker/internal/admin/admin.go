// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package admin provides bindings for the crosskylabadmin API
package admin

import (
	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/libs/skylab/inventory"
)

// NewInventoryClient creates a new inventory RPC client.
func NewInventoryClient(url string) (*fleet.InventoryClient, error) {
	// TODO(ayatane): implement
	return nil, nil
}

// UpdateLabels calls the admin service update labels API.
func UpdateLabels(c *fleet.InventoryClient, dutID string, new *inventory.SchedulableLabels) error {
	// TODO(ayatane): implement
	return nil
}
