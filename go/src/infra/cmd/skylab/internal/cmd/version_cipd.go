// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"context"
	"net/http"

	"go.chromium.org/luci/cipd/client/cipd"
	"go.chromium.org/luci/common/errors"
)

const service = "https://chrome-infra-packages.appspot.com"

// describe returns information about a package instances.
func describe(ctx context.Context, pkg, version string) (*cipd.InstanceDescription, error) {
	opts := cipd.ClientOptions{
		ServiceURL:      service,
		AnonymousClient: http.DefaultClient,
	}
	client, err := cipd.NewClient(opts)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	pin, err := client.ResolveVersion(ctx, pkg, version)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	d, err := client.DescribeInstance(ctx, pin, nil)
	if err != nil {
		return nil, errors.Annotate(err, "describe package").Err()
	}
	return d, nil
}
