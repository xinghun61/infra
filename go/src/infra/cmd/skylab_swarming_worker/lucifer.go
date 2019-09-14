// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"
	"log"
	"os"
	"os/exec"
	"strings"

	"infra/cmd/skylab_swarming_worker/internal/event"
	"infra/cmd/skylab_swarming_worker/internal/swmbot"
	"infra/cmd/skylab_swarming_worker/internal/swmbot/harness"
)

type luciferResult struct {
	TestsFailed int
}

// runLuciferCommand runs a Lucifer exec.Cmd and processes Lucifer events.
func runLuciferCommand(i *harness.Info, w io.Writer, cmd *exec.Cmd) (*luciferResult, error) {
	log.Printf("Running %s %s", cmd.Path, strings.Join(cmd.Args, " "))
	cmd.Stderr = os.Stderr

	r := &luciferResult{}
	if w == nil {
		w = os.Stdout
	}
	f := func(e event.Event, m string) {
		switch {
		case e == event.TestFailed && m != "autoserv":
			r.TestsFailed++
		case isHostStatus(e):
			s := hostStateUpdates[e]
			log.Printf("Got host event '%s', set host state to %s", e, s)
			i.BotInfo.HostState = s
		default:
		}
	}
	err := event.RunCommand(cmd, f)
	return r, err
}

// hostStateUpdates maps Events to the target runtime state of the
// host.  Host events that don't need to be handled are left as
// comment placeholders to aid cross-referencing.
var hostStateUpdates = map[event.Event]swmbot.HostState{
	event.HostClean:        swmbot.HostReady,
	event.HostNeedsCleanup: swmbot.HostNeedsCleanup,
	event.HostNeedsRepair:  swmbot.HostNeedsRepair,
	event.HostNeedsReset:   swmbot.HostNeedsReset,
	event.HostReady:        swmbot.HostReady,
	// event.HostReadyToRun
	// event.HostRunning
	event.HostFailedRepair: swmbot.HostRepairFailed,
}

func isHostStatus(e event.Event) bool {
	_, ok := hostStateUpdates[e]
	return ok
}
