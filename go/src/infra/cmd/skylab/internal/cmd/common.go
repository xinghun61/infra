// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"flag"
	"fmt"
	"net/http"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab/internal/site"
)

const progName = "skylab"

type envFlags struct {
	dev bool
}

func (f *envFlags) Register(fl *flag.FlagSet) {
	fl.BoolVar(&f.dev, "dev", false, "Run in dev environment")
}

func (f envFlags) Env() site.Environment {
	if f.dev {
		return site.Dev
	}
	return site.Prod
}

// httpClient returns an HTTP client with authentication set up.
func httpClient(ctx context.Context, f *authcli.Flags) (*http.Client, error) {
	o, err := f.Options()
	if err != nil {
		return nil, errors.Annotate(err, "failed to get auth options").Err()
	}
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, o)
	c, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client").Err()
	}
	return c, nil

}

const swarmingAPISuffix = "_ah/api/swarming/v1/"

func newSwarmingService(service string, c *http.Client) (*swarming.Service, error) {
	s, err := swarming.New(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create Swarming client for host %s", service).Err()
	}
	s.BasePath = service + swarmingAPISuffix
	return s, nil
}

func swarmingTaskURL(e site.Environment, taskID string) string {
	return fmt.Sprintf("%stask?id=%s", e.SwarmingService, taskID)
}
