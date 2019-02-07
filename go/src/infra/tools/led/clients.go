// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"
	"os"

	"golang.org/x/net/context"

	"go.chromium.org/luci/auth"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
)

func newSwarmClient(ctx context.Context, authOpts auth.Options, swarmingHost string) (*http.Client, *swarming.Service, error) {
	authClient, err := getAuthClient(ctx, authOpts)
	if err != nil {
		return nil, nil, err
	}

	swarm, err := swarming.New(authClient)
	if err != nil {
		return nil, nil, err
	}
	swarm.BasePath = fmt.Sprintf("https://%s/_ah/api/swarming/v1/", swarmingHost)
	return authClient, swarm, nil
}

func getAuthClient(ctx context.Context, authOpts auth.Options) (*http.Client, error) {
	authenticator := auth.NewAuthenticator(ctx, auth.SilentLogin, authOpts)
	authClient, err := authenticator.Client()
	if err == auth.ErrLoginRequired {
		fmt.Fprintln(os.Stderr, "Login required: run `led auth-login`.")
		os.Exit(1)
	}
	return authClient, err
}
