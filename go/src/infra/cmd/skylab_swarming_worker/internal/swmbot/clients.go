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

// ClientAuth returns auth Options for creating admin RPC clients for
// the current Swarming bot task.
func ClientAuth(ctx context.Context) (auth.Options, error) {
	ctx, err := lucictx.SwitchLocalAccount(ctx, "task")
	if err != nil {
		return auth.Options{}, errors.Annotate(err, "create client auth options").Err()
	}
	o := auth.Options{
		Method: auth.LUCIContextMethod,
		Scopes: []string{
			auth.OAuthScopeEmail,
			"https://www.googleapis.com/auth/cloud-platform",
		},
	}
	return o, nil
}

// InventoryClient returns an InventoryClient for the current Swarming bot task.
func InventoryClient(ctx context.Context, b *Info) (fleet.InventoryClient, error) {
	o, err := ClientAuth(ctx)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory client").Err()
	}
	c, err := admin.NewInventoryClient(ctx, b.AdminService, o)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory client").Err()
	}
	return c, nil
}
