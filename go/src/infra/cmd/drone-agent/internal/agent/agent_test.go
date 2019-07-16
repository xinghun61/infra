// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package agent

import (
	"context"
	"io/ioutil"
	"os"
	"sort"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/google/go-cmp/cmp"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/draining"
)

func TestAgent_add_duts_and_drain_agent(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	s := f.waitForState()
	t.Run("added assigned DUTs", func(t *testing.T) {
		got := receiveStrings(s.addedDUTs, 2)
		sort.Strings(got)
		want := []string{"claudia", "ryza"}
		if diff := cmp.Diff(want, got); diff != "" {
			t.Errorf("assigned DUTs mismatch (-want +got):\n%s", diff)
		}
	})
	drain()
	t.Run("drained all DUTs", func(t *testing.T) {
		select {
		case <-s.drainedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected DrainAll event")
		}
	})
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

func TestAgent_cancel_agent(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	s := f.waitForState()
	cancel()
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminatedAll event")
		}
	})
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after canceling")
		}
	})
}

func TestAgent_dont_add_draining_duts(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	c.res.DrainingDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()
	s := f.waitForState()

	t.Run("don't add draining DUTs", func(t *testing.T) {
		// TODO(ayatane): Testing for bad behavior here is
		// flaky.  We can make this more reliable by detecting
		// report cycles in the agent.
		select {
		case d := <-s.addedDUTs:
			t.Errorf("Added DUT %v; want no DUTs added", d)
		case <-time.After(time.Millisecond):
		}
	})
	t.Run("draining DUTs are released", func(t *testing.T) {
		got := receiveStrings(s.drainedDUTs, 2)
		sort.Strings(got)
		want := []string{"claudia", "ryza"}
		if diff := cmp.Diff(want, got); diff != "" {
			t.Errorf("drained DUTs mismatch (-want +got):\n%s", diff)
		}
	})
	drain()
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

func TestAgent_add_duts_and_drain_duts(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	s := f.waitForState()
	t.Run("added assigned DUTs", func(t *testing.T) {
		got := receiveStrings(s.addedDUTs, 2)
		sort.Strings(got)
		want := []string{"claudia", "ryza"}
		if diff := cmp.Diff(want, got); diff != "" {
			t.Errorf("assigned DUTs mismatch (-want +got):\n%s", diff)
		}
	})
	c.withLock(func() {
		c.res.DrainingDuts = []string{"ryza"}
	})
	t.Run("drained DUTs", func(t *testing.T) {
		select {
		case d := <-s.drainedDUTs:
			if d != "ryza" {
				t.Errorf("Got drained DUT %v; want ryza", d)
			}
		case <-time.After(time.Second):
			t.Errorf("DUT not drained")
		}
	})
	drain()
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

func TestAgent_unknown_uuid_causes_termination(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	s := f.waitForState()
	c.withLock(func() { c.res.Status = api.ReportDroneResponse_UNKNOWN_UUID })
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminateAll event")
		}
	})
	drain()
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

func TestAgent_expiration_causes_termination(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newStubClient()
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	s := f.waitForState()
	c.withLock(func() { c.res.ExpirationTime = protoTime(time.Now()) })
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminateAll event")
		}
	})
	drain()
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

func TestAgent_draining_reports_lame_duck_mode(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := newSpyClient()
	a.Client = c
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()

	drain()
drainEvents:
	for {
		select {
		case <-c.reports:
		default:
			break drainEvents
		}
	}
	t.Run("agent reports lame duck", func(t *testing.T) {
		res := <-c.reports
		if got := res.LoadIndicators.DutCapacity; got != 0 {
			t.Errorf("agent reported DutCapacity %v; want 0", got)
		}
	})
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit after draining")
		}
	})
}

// newTestAgent makes a new agent for tests with common values.  Tests
// MUST NOT depend on the exact values here.  If something is
// important to a test, the test should explicitly set the value.
func newTestAgent(t *testing.T) (a *Agent, cleanup func()) {
	t.Helper()
	workDir, err := ioutil.TempDir("", "test")
	if err != nil {
		t.Fatal(err)
	}
	cleanup = func() { os.RemoveAll(workDir) }
	a = &Agent{
		SwarmingURL:       "https://swarming.example.com",
		WorkingDir:        workDir,
		ReportingInterval: time.Nanosecond,
		DUTCapacity:       99999,
		logger:            testLogger{t},
		startBotFunc:      startFakeBot,
	}
	return a, cleanup
}

// testLogger implements the logger interface for tests.
type testLogger struct {
	t *testing.T
}

func (t testLogger) Printf(format string, args ...interface{}) {
	t.t.Logf(format, args...)
}

// protoTime returns a protobuf time type.
func protoTime(t time.Time) *timestamp.Timestamp {
	t2, err := ptypes.TimestampProto(t)
	if err != nil {
		panic(err)
	}
	return t2
}

// receiveStrings receives N strings from the channel and returns them
// as a slice.
func receiveStrings(c <-chan string, n int) []string {
	s := make([]string, n)
	for i := range s {
		s[i] = <-c
	}
	return s
}
