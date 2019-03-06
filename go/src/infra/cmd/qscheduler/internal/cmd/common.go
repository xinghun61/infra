// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"flag"
	"net/http"
	"strconv"

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

func prpcClient(ctx context.Context, a *authcli.Flags, e *envFlags) (*prpc.Client, error) {
	h, err := httpClient(ctx, a)
	if err != nil {
		return nil, err
	}

	return &prpc.Client{
		C:       h,
		Host:    e.Env().QSchedulerHost,
		Options: site.DefaultPRPCOptions,
	}, nil
}

func newAdminClient(ctx context.Context, a *authcli.Flags, e *envFlags) (qscheduler.QSchedulerAdminClient, error) {
	p, err := prpcClient(ctx, a, e)
	if err != nil {
		return nil, err
	}

	return qscheduler.NewQSchedulerAdminPRPCClient(p), nil
}

func newViewClient(ctx context.Context, a *authcli.Flags, e *envFlags) (qscheduler.QSchedulerViewClient, error) {
	p, err := prpcClient(ctx, a, e)
	if err != nil {
		return nil, err
	}

	return qscheduler.NewQSchedulerViewPRPCClient(p), nil
}

func toFloats(s []string) ([]float32, error) {
	floats := make([]float32, len(s))
	for i, c := range s {
		f, err := strconv.ParseFloat(c, 32)
		if err != nil {
			return nil, err
		}
		floats[i] = float32(f)
	}
	return floats, nil
}
