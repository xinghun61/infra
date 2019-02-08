// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package admin provides bindings for the crosskylabadmin API
package admin

import (
	"context"
	"net/http"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	fleet "infra/appengine/crosskylabadmin/api/fleet/v1"
)

// NewInventoryClient creates a new inventory RPC client.
func NewInventoryClient(ctx context.Context, url string, o auth.Options) (fleet.InventoryClient, error) {
	hc, err := httpClient(ctx, o)
	if err != nil {
		return nil, errors.Annotate(err, "create inventory admin client").Err()
	}
	pc := prpc.Client{
		C:    hc,
		Host: url,
	}
	ic := fleet.NewInventoryPRPCClient(&pc)
	return ic, nil
}

// httpClient returns an HTTP client with authentication set up.
func httpClient(ctx context.Context, o auth.Options) (*http.Client, error) {
	a := auth.NewAuthenticator(ctx, auth.SilentLogin, o)
	c, err := a.Client()
	if err != nil {
		return nil, err
	}
	return c, nil

}
