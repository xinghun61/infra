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
)

const drainingFilePath = "/var/spool/drone-agent-draining"

func main() {
	ctx := context.Background()
	ctx = notifySIGTERM(ctx)
	ctx = notifyDraining(ctx, drainingFilePath)
	var a agent
	a.run(ctx)
}
