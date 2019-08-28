// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build !windows

// Command drone-agent is the client that talks to the drone queen
// service to provide Swarming bots for running tasks against test
// devices.  See the README.
package main

import (
	"context"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/agent"
	"infra/cmd/drone-agent/internal/bot"
	"infra/cmd/drone-agent/internal/draining"
)

const drainingFile = "drone-agent.drain"

var (
	queenService = os.Getenv("DRONE_AGENT_QUEEN_SERVICE")
	// DRONE_AGENT_SWARMING_URL is the URL of the Swarming
	// instance.  Should be a full URL without the path,
	// e.g. https://host.example.com
	swarmingURL       = os.Getenv("DRONE_AGENT_SWARMING_URL")
	dutCapacity       = getIntEnv("DRONE_AGENT_DUT_CAPACITY", 10)
	reportingInterval = time.Duration(getIntEnv("DRONE_AGENT_REPORTING_INTERVAL_MINS", 1)) * time.Minute

	authOptions = auth.Options{
		Method:                 auth.ServiceAccountMethod,
		ServiceAccountJSONPath: os.Getenv("GOOGLE_APPLICATION_CREDENTIALS"),
	}
	workingDirPath = filepath.Join(os.Getenv("HOME"), "skylab_bots")
)

func main() {
	// TODO(ayatane): Add environment validation.
	ctx := context.Background()
	ctx = notifySIGTERM(ctx)
	ctx = notifyDraining(ctx, filepath.Join(workingDirPath, drainingFile))
	authn := auth.NewAuthenticator(ctx, auth.SilentLogin, authOptions)
	if err := os.MkdirAll(workingDirPath, 0777); err != nil {
		log.Fatal(err)
	}
	c, err := droneClient(ctx, authn, queenService)
	if err != nil {
		log.Fatal(err)
	}
	a := agent.Agent{
		Client:            c,
		SwarmingURL:       swarmingURL,
		WorkingDir:        workingDirPath,
		ReportingInterval: reportingInterval,
		DUTCapacity:       dutCapacity,
		StartBotFunc:      bot.NewStarter().Start,
	}
	a.Run(ctx)
}

func droneClient(ctx context.Context, a *auth.Authenticator, queenService string) (api.DroneClient, error) {
	h, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	return api.NewDronePRPCClient(&prpc.Client{
		C:    h,
		Host: queenService,
	}), nil
}

const checkDrainingInterval = time.Minute

// notifyDraining returns a context that is marked as draining when a
// file exists at the given path.
func notifyDraining(ctx context.Context, path string) context.Context {
	ctx, drain := draining.WithDraining(ctx)
	_, err := os.Stat(path)
	if err == nil {
		drain()
		return ctx
	}
	go func() {
		for {
			time.Sleep(checkDrainingInterval)
			_, err := os.Stat(path)
			if err == nil {
				drain()
				return
			}
		}
	}()
	return ctx
}

// getIntEnv gets an int value from an environment variable.  If the
// environment variable is not valid or is not set, use the default value.
func getIntEnv(key string, defaultValue int) int {
	v, ok := os.LookupEnv(key)
	if !ok {
		return defaultValue
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		log.Printf("Invalid %s, using default value (error: %v)", key, err)
		return defaultValue
	}
	return n
}
