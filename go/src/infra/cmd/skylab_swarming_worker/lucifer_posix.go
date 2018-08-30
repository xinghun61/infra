// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build darwin linux

package main

import (
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"strings"

	"golang.org/x/sys/unix"

	"infra/cmd/skylab_swarming_worker/internal/annotee"
	"infra/cmd/skylab_swarming_worker/internal/event"
	"infra/cmd/skylab_swarming_worker/internal/log"
	"infra/cmd/skylab_swarming_worker/internal/lucifer"
	"infra/cmd/skylab_swarming_worker/internal/swarming"
	"infra/cmd/skylab_swarming_worker/internal/swarming/botcache"
)

type luciferResult struct {
	TestsFailed int
}

func runLuciferJob(b *swarming.Bot, w io.Writer, r lucifer.RunJobArgs) (*luciferResult, error) {
	cmd := lucifer.RunJobCommand(b.LuciferConfig(), r)
	c := make(chan os.Signal, 1)
	defer close(c)
	signal.Notify(c, unix.SIGTERM, unix.SIGINT)
	defer signal.Stop(c)
	go listenAndAbort(c, r.AbortSock)
	return runLuciferCommand(b, w, cmd)
}

func runLuciferAdminTask(b *swarming.Bot, w io.Writer, r lucifer.AdminTaskArgs) (*luciferResult, error) {
	cmd := lucifer.AdminTaskCommand(b.LuciferConfig(), r)
	c := make(chan os.Signal)
	defer close(c)
	signal.Notify(c, unix.SIGTERM, unix.SIGINT)
	defer signal.Stop(c)
	go listenAndAbort(c, r.AbortSock)
	return runLuciferCommand(b, w, cmd)
}

// listenAndAbort sends an abort to an abort socket when signals are
// received.  This function is intended to be used as a goroutine for
// handling signals.  This function returns when the channel is
// closed.
func listenAndAbort(c <-chan os.Signal, path string) {
	for range c {
		if err := abort(path); err != nil {
			log.Printf("Error sending abort for signal: %s", err)
		}
	}
}

// abort sends an abort datagram to the socket at the given path.
func abort(path string) error {
	c, err := net.Dial("unixgram", path)
	if err != nil {
		return err
	}
	// The value sent does not matter.
	b := []byte("abort")
	_, err = c.Write(b)
	return err
}

// runLuciferCommand runs a Lucifer exec.Cmd and processes Lucifer events.
func runLuciferCommand(b *swarming.Bot, w io.Writer, cmd *exec.Cmd) (*luciferResult, error) {
	log.Printf("Running %s %s", cmd.Path, strings.Join(cmd.Args, " "))
	cmd.Stderr = os.Stderr

	r := &luciferResult{}
	if w == nil {
		w = os.Stdout
	}
	c := annotee.NewClient(w)
	defer c.Close()
	f := func(e event.Event, m string) {
		switch {
		case isTaskStatus(e):
			c.OpenStep(string(e))
			if e == event.TestFailed && m != "autoserv" {
				r.TestsFailed++
			}
		case isHostStatus(e):
			s := hostStateUpdates[e]
			log.Printf("Got host event '%s', set host state to %s", e, s)
			b.BotInfo.HostState = s
		default:
			log.Printf("Unexpected lucifer event: %s", e)
		}
	}
	err := event.RunCommand(cmd, f)
	c.AddLink("results", resultsURL(b))
	return r, err
}

func resultsURL(b *swarming.Bot) string {
	return fmt.Sprintf(
		"https://stainless.corp.google.com/browse/chromeos-autotest-results/swarming-%s/",
		b.Task.ID)
}

// taskStateUpdates is the set of Events that correspond to task state updates.
var taskStateUpdates = map[event.Event]bool{
	// Job state changes
	event.Starting:     true,
	event.Provisioning: true,
	event.Running:      true,
	event.Gathering:    true,
	event.Parsing:      true,
	event.Completed:    true,

	// Test status changes
	event.TestPassed: true,
	event.TestFailed: true,
}

// hostStateUpdates maps Events to the target runtime state of the
// host.  Host events that don't need to be handled are left as
// comment placeholders to aid cross-referencing.
var hostStateUpdates = map[event.Event]botcache.HostState{
	event.HostClean:        botcache.HostReady,
	event.HostNeedsCleanup: botcache.HostNeedsCleanup,
	event.HostNeedsRepair:  botcache.HostNeedsRepair,
	event.HostNeedsReset:   botcache.HostNeedsReset,
	event.HostReady:        botcache.HostReady,
	// event.HostReadyToRun
	// event.HostRunning
	event.HostFailedRepair: botcache.HostRepairFailed,
}

func isTaskStatus(e event.Event) bool {
	return taskStateUpdates[e]
}

func isHostStatus(e event.Event) bool {
	_, ok := hostStateUpdates[e]
	return ok
}
