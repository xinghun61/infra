// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package event standardizes communication of events from Lucifer commands.

Events are sent by printing to stdout.

Changes must be backward compatible with handlers.  Currently, there
is a handler for Skylab (skylab_swarming_worker) and one for Autotest
(job_reporter).  The Autotest handler is implemented with the Python
eventlib module.
*/
package event

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"os/exec"
	"strings"
)

// Event is a string enum type for valid events to pass to Send and
// SendWithMsg.  Handler functions should be able to handle all of
// these.
type Event string

// Task status events.
const (
	// Starting indicates that the task is beginning to run.
	Starting Event = "starting"
	// The following events indicate task status.  The handler may
	// use these to track task status.
	Provisioning Event = "provisioning"
	Running      Event = "running"
	Gathering    Event = "gathering"
	Parsing      Event = "parsing"
	Aborted      Event = "aborted"
	// Completed indicates that the task has completed.  The
	// handler may run any post-task logic on receiving this
	// event.
	Completed Event = "completed"
)

// Test status events.
const (
	TestPassed Event = "test_passed"
	TestFailed Event = "test_failed"
)

// Host status events.
const (
	// HostClean indicates that the host is ready to run tests and
	// that it is clean.  The handler should mark the host as not
	// dirty if the handler is tracking host dirtiness.  HostClean
	// should be considered a superset of HostReady.
	HostClean        Event = "host_clean"
	HostFailedRepair Event = "host_failed_repair"
	HostNeedsCleanup Event = "host_needs_cleanup"
	HostNeedsRepair  Event = "host_needs_repair"
	HostNeedsReset   Event = "host_needs_reset"
	// HostReady indicates that the host is ready to run tests.
	// HostReady should not be sent together with HostClean.
	HostReady Event = "host_ready"
	// HostReadyToRun indicates that the host is ready to run
	// tests, after provisioning and before running tests as part
	// of a Lucifer task.  This is a transitory state, not a final
	// state like HostReady.
	HostReadyToRun Event = "host_ready_to_run"
	// HostRunning indicates that the host is running a test.  The
	// handler may mark the host as dirty if the handler is
	// tracking host dirtiness.
	HostRunning Event = "host_running"
)

// SendWithMsg sends an event with a message by printing to stdout.
// The message should not contain newlines, non-ASCII characters,
// non-printable characters, or trailing whitespace.
func SendWithMsg(e Event, m string) {
	log.Printf("Sending event %s with message %s", e, m)
	if _, err := fmt.Printf("%s %s\n", e, m); err != nil {
		log.Panicf("Sending event %s failed: %s", e, err)
	}
}

// Send sends an event by printing to stdout.
func Send(e Event) {
	log.Printf("Sending event %s", e)
	if _, err := fmt.Println(e); err != nil {
		log.Panicf("Sending event %s failed: %s", e, err)
	}
}

// Handler is the type for valid functions to pass to Handle.
type Handler func(e Event, m string)

// RunCommand runs an exec.Cmd that uses the event protocol and calls
// Handle on with the provided handler function to handle events.
func RunCommand(c *exec.Cmd, f Handler) error {
	r, err := c.StdoutPipe()
	if err != nil {
		return err
	}
	if err := c.Start(); err != nil {
		return err
	}
	hErr := Handle(r, f)
	if err := c.Wait(); err != nil {
		return err
	}
	return hErr
}

// Handle handles events read from an io.Reader.  The handler function
// is called for each event with the event and message strings.  Use a
// closure to keep state or to store errors.  This function only
// returns an error if event parsing fails.
func Handle(r io.Reader, f Handler) error {
	s := bufio.NewScanner(r)
	for s.Scan() {
		toks := strings.SplitN(s.Text(), " ", 2)
		e := Event(toks[0])
		var m string
		if len(toks) == 2 {
			m = toks[1]
		}
		f(e, m)
	}
	return s.Err()
}
