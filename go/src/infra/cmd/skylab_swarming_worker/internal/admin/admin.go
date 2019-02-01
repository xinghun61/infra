// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package admin provides bindings for the crosskylabadmin API
package admin

import "infra/libs/skylab/inventory"

// UpdateLabels calls the admin service update labels API.
func UpdateLabels(dutID string, old, new *inventory.SchedulableLabels) error {
	// TODO(ayatane): implement
	return nil
}
