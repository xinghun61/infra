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
	"sync"
	"time"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/grpc/prpc"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/agent"
	"infra/cmd/drone-agent/internal/bot"
	"infra/cmd/drone-agent/internal/draining"
	"infra/cmd/drone-agent/internal/tokman"
)

const (
	drainingFile   = "drone-agent.drain"
	oauthTokenPath = "/var/lib/swarming/oauth_bot_token.json"
)

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
	if err := innerMain(); err != nil {
		log.Fatal(err)
	}
}

func innerMain() error {
	// TODO(ayatane): Add environment validation.
	ctx := context.Background()
	ctx = notifySIGTERM(ctx)
	ctx = notifyDraining(ctx, filepath.Join(workingDirPath, drainingFile))

	var wg sync.WaitGroup
	defer wg.Wait()

	authn := auth.NewAuthenticator(ctx, auth.SilentLogin, authOptions)

	r, err := tokman.Make(authn, oauthTokenPath, time.Minute)
	if err != nil {
		return err
	}
	wg.Add(1)
	go func() {
		r.KeepNew(ctx)
		wg.Done()
	}()

	h, err := authn.Client()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(workingDirPath, 0777); err != nil {
		return err
	}

	a := agent.Agent{
		Client: api.NewDronePRPCClient(&prpc.Client{
			C:    h,
			Host: queenService,
		}),
		SwarmingURL:       swarmingURL,
		WorkingDir:        workingDirPath,
		ReportingInterval: reportingInterval,
		DUTCapacity:       dutCapacity,
		StartBotFunc:      bot.NewStarter(h).Start,
	}
	a.Run(ctx)
	return nil
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
