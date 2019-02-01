// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"strings"

	"infra/cmd/skylab_swarming_worker/internal/annotations"
	"infra/cmd/skylab_swarming_worker/internal/botinfo"
	"infra/cmd/skylab_swarming_worker/internal/event"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/harness"
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
	annotations.BuildStep(w, "Epilog")
	annotations.StepLink(w, "Task results (Stainless)", resultsURL(i.Bot))
	annotations.StepClosed(w)
	return r, err
}

func resultsURL(b *swarming.Bot) string {
	return fmt.Sprintf(
		"https://stainless.corp.google.com/browse/chromeos-autotest-results/swarming-%s/",
		b.Task.ID)
}

// hostStateUpdates maps Events to the target runtime state of the
// host.  Host events that don't need to be handled are left as
// comment placeholders to aid cross-referencing.
var hostStateUpdates = map[event.Event]botinfo.HostState{
	event.HostClean:        botinfo.HostReady,
	event.HostNeedsCleanup: botinfo.HostNeedsCleanup,
	event.HostNeedsRepair:  botinfo.HostNeedsRepair,
	event.HostNeedsReset:   botinfo.HostNeedsReset,
	event.HostReady:        botinfo.HostReady,
	// event.HostReadyToRun
	// event.HostRunning
	event.HostFailedRepair: botinfo.HostRepairFailed,
}

func isHostStatus(e event.Event) bool {
	_, ok := hostStateUpdates[e]
	return ok
}
