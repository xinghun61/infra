// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"flag"
	"net/http"

	"go.chromium.org/luci/auth"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/grpc/prpc"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/cmd/qscheduler/internal/site"
)

const progName = "qscheduler"

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

func newAdminClient(ctx context.Context, a *authcli.Flags, e *envFlags) (qscheduler.QSchedulerAdminClient, error) {
	h, err := httpClient(ctx, a)
	if err != nil {
		return nil, err
	}

	p := &prpc.Client{
		C:       h,
		Host:    e.Env().QSchedulerHost,
		Options: site.DefaultPRPCOptions,
	}

	return qscheduler.NewQSchedulerAdminPRPCClient(p), nil
}
