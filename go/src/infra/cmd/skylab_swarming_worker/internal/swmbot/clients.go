// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swmbot

import (
	"context"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/lucictx"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
	"infra/cmd/skylab_swarming_worker/internal/admin"
)

// WithTaskAccount returns a context using the Swarming task service
// account.
func WithTaskAccount(ctx context.Context) (context.Context, error) {
	return lucictx.SwitchLocalAccount(ctx, "task")
}

// WithSystemAccount returns acontext to using the Swarming bot system
// service account.
func WithSystemAccount(ctx context.Context) (context.Context, error) {
	return lucictx.SwitchLocalAccount(ctx, "system")
}

// InventoryClient returns an InventoryClient for the current Swarming
// bot task.  The context should use an explicit service account using
// WithTaskAccount or WithSystemAccount; otherwise the default service
// account is used.
func InventoryClient(ctx context.Context, b *Info) (fleet.InventoryClient, error) {
	o := auth.Options{
		Method: auth.LUCIContextMethod,
		Scopes: []string{
			auth.OAuthScopeEmail,
			"https://www.googleapis.com/auth/cloud-platform",
		},
	}
	c, err := admin.NewInventoryClient(ctx, b.AdminService, o)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory client").Err()
	}
	return c, nil
}
