// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"net/http"

	"golang.org/x/net/context"

	swarming "github.com/luci/luci-go/common/api/swarming/swarming/v1"
	"github.com/luci/luci-go/common/auth"
)

func newSwarmClient(ctx context.Context, authOpts auth.Options, swarmingServer string) (*http.Client, *swarming.Service, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err != nil {
		return nil, nil, err
	}

	swarm, err := swarming.New(authClient)
	if err != nil {
		return nil, nil, err
	}
	swarm.BasePath = swarmingServer + "/api/swarming/v1/"
	return authClient, swarm, nil
}
