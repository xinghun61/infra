// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"golang.org/x/net/context"
)

type cipdClient struct {
	serviceURL string
}

func (c cipdClient) fixServerArgs(args []string) []string {
	newArgs := args
	if c.serviceURL != "" {
		newArgs = append(append([]string(nil), args...), "-service-url", c.serviceURL)
	}
	return newArgs
}

func (c cipdClient) server(ctx context.Context, args ...string) error {
	return newRunner(ctx, "cipdClient.server", "cipd", c.fixServerArgs(args)).do()
}

func (c cipdClient) serverQuiet(ctx context.Context, args ...string) error {
	run := newRunner(ctx, "cipdClient.server", "cipd", c.fixServerArgs(args))
	run.suppressFail = true
	return run.do()
}

func (c cipdClient) local(ctx context.Context, args ...string) error {
	return newRunner(ctx, "cipdClient.local", "cipd", args).do()
}
