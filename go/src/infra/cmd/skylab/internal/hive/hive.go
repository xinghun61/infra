// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package hive wraps Swarming access for the skylab command.
package hive

import (
	"context"

	"go.chromium.org/luci/auth"
	swarming "go.chromium.org/luci/common/api/swarming/swarming/v1"
	"go.chromium.org/luci/common/errors"
)

const apiSuffix = "_ah/api/swarming/v1/"

// NewSwarmingService returns a Service for interacting with Swarming.
func NewSwarmingService(ctx context.Context, service string, o auth.Options) (*swarming.Service, error) {
	a := auth.NewAuthenticator(ctx, auth.OptionalLogin, o)
	c, err := a.Client()
	if err != nil {
		return nil, errors.Annotate(err, "failed to create HTTP client for %s", service).Err()
	}
	s, err := swarming.New(c)
	if err != nil {
		return nil, errors.Annotate(err, "failed to create Swarming client for host %s", service).Err()
	}
	s.BasePath = service + apiSuffix
	return s, nil
}
