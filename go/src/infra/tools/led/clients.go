// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"

	"golang.org/x/net/context"

	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/auth"
)

func newSwarmClient(ctx context.Context, authOpts auth.Options, swarmingHost string) (*auth.Authenticator, *http.Client, *swarming.Service, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		return nil, nil, nil, err
	}

	swarm, err := swarming.New(authClient)
	if err != nil {
		return nil, nil, nil, err
	}
	swarm.BasePath = fmt.Sprintf("https://%s/api/swarming/v1/", swarmingHost)
	return authenticator, authClient, swarm, nil
}
