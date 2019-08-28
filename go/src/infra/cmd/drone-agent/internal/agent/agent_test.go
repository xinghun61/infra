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
	"infra/cmd/drone-agent/internal/bot"
	"infra/cmd/drone-agent/internal/draining"
)

func TestAgent_add_duts_and_drain_agent(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
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
	testAgentExits(t, done)
}

func TestAgent_cancel_agent(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	cancel()
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminatedAll event")
		}
	})
	testAgentExits(t, done)
}

func TestAgent_dont_add_draining_duts(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectSpyClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	c.res.DrainingDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	t.Run("don't add draining DUTs", func(t *testing.T) {
	drainChannel:
		for {
			select {
			case <-c.reports:
			default:
				break drainChannel
			}
		}
		select {
		case <-c.reports:
		case <-time.After(time.Second):
			t.Fatalf("agent did not call ReportDrone")
		}
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
	testAgentExits(t, done)
}

func TestAgent_add_duts_and_drain_duts(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
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
	testAgentExits(t, done)
}

func TestAgent_unknown_uuid(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	c.withLock(func() {
		c.res.Status = api.ReportDroneResponse_UNKNOWN_UUID
	})
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminateAll event")
		}
	})
	c.withLock(func() {
		c.res.Status = api.ReportDroneResponse_OK
	})
	t.Run("create new state", func(t *testing.T) {
		select {
		case <-f.states:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected new state")
		}
	})
	drain()
	testAgentExits(t, done)
}

func TestAgent_expiration(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	c.withLock(func() {
		c.res.ExpirationTime = protoTime(time.Now())
	})
	t.Run("terminated all DUTs", func(t *testing.T) {
		select {
		case <-s.terminatedAll:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected TerminateAll event")
		}
	})
	t.Run("create new state", func(t *testing.T) {
		select {
		case <-f.states:
		case <-time.After(time.Second):
			t.Errorf("Did not get expected new state")
		}
	})
	drain()
	testAgentExits(t, done)
}

func TestAgent_draining_reports_lame_duck_mode(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectSpyClient(a)
	c.res.AssignedDuts = []string{"ryza"}
	b := newPersistentBot()
	started := make(chan struct{}, 1)
	a.StartBotFunc = func(bot.Config) (bot.Bot, error) {
		select {
		case started <- struct{}{}:
		default:
		}
		return b, nil
	}

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	select {
	case <-started:
	case <-time.After(time.Second):
		t.Errorf("agent did not start assigned bot")
	}
	drain()
	t.Run("agent reports lame duck", func(t *testing.T) {
		now := time.Now()
	checkReports:
		for {
			select {
			case res := <-c.reports:
				if got := res.LoadIndicators.DutCapacity; got == 0 {
					break checkReports
				}
			case <-time.After(time.Second):
				t.Errorf("agent did not call ReportDrone")
			}
			if time.Now().Sub(now) > time.Second {
				t.Errorf("agent did not report lame duck")
				break checkReports
			}
		}
	})
	b.Stop()
	testAgentExits(t, done)
}

func TestAgent_keep_reporting_while_draining(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectSpyClient(a)
	c.res.AssignedDuts = []string{"ryza"}
	b := newPersistentBot()
	started := make(chan struct{}, 1)
	a.StartBotFunc = func(bot.Config) (bot.Bot, error) {
		select {
		case started <- struct{}{}:
		default:
		}
		return b, nil
	}

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	select {
	case <-started:
	case <-time.After(time.Second):
		t.Errorf("agent did not start assigned bot")
	}
	drain()
	t.Run("agent keeps reporting", func(t *testing.T) {
		for i := 1; i < 3; i++ {
			select {
			case <-c.reports:
			case <-time.After(time.Second):
				t.Errorf("agent did not call ReportDrone")
			}
		}
	})
	b.Stop()
	testAgentExits(t, done)
}

func TestAgent_keep_reporting_while_terminating(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectSpyClient(a)
	c.res.AssignedDuts = []string{"ryza"}
	b := newPersistentBot()
	started := make(chan struct{}, 1)
	a.StartBotFunc = func(bot.Config) (bot.Bot, error) {
		select {
		case started <- struct{}{}:
		default:
		}
		return b, nil
	}

	// Start running.
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	done := runWithDoneChannel(ctx, a)

	select {
	case <-started:
	case <-time.After(time.Second):
		t.Errorf("agent did not start assigned bot")
	}
	cancel()
	t.Run("agent keeps reporting", func(t *testing.T) {
		for i := 1; i < 3; i++ {
			select {
			case <-c.reports:
			case <-time.After(time.Second):
				t.Errorf("agent did not call ReportDrone")
			}
		}
	})
	b.Stop()
	testAgentExits(t, done)
}

func TestAgent_terminate_unassigned_duts(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectStubClient(a)
	c.res.AssignedDuts = []string{"ryza", "claudia"}
	f := injectStateSpyFactory(a)

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	t.Run("added assigned DUTs", func(t *testing.T) {
		got := receiveStrings(s.addedDUTs, 2)
		sort.Strings(got)
		want := []string{"claudia", "ryza"}
		if diff := cmp.Diff(want, got); diff != "" {
			t.Errorf("assigned DUTs mismatch (-want +got):\n%s", diff)
		}
	})
	c.withLock(func() {
		c.res.AssignedDuts = []string{"ryza"}
	})
	t.Run("terminated unassigned DUTs", func(t *testing.T) {
		select {
		case d := <-s.terminatedDUTs:
			if d != "claudia" {
				t.Errorf("Got terminated DUT %v; want claudia", d)
			}
		case <-time.After(time.Second):
			t.Errorf("Did not get expected DUT termination")
		}
	})
	drain()
	testAgentExits(t, done)
}

func TestAgent_block_new_duts_when_draining(t *testing.T) {
	t.Parallel()
	a, cleanup := newTestAgent(t)
	defer cleanup()

	// Set up agent.
	c := injectSpyClient(a)
	c.res.AssignedDuts = []string{"ryza"}
	f := injectStateSpyFactory(a)
	b := newPersistentBot()
	started := make(chan struct{}, 1)
	a.StartBotFunc = func(bot.Config) (bot.Bot, error) {
		select {
		case started <- struct{}{}:
		default:
		}
		return b, nil
	}

	// Start running.
	ctx := context.Background()
	ctx, drain := draining.WithDraining(ctx)
	done := runWithDoneChannel(ctx, a)

	s := <-f.states
	select {
	case <-started:
	case <-time.After(time.Second):
		t.Errorf("agent did not start assigned bot")
	}
	drain()
	t.Run("agent blocks new DUTs", func(t *testing.T) {
		select {
		case <-s.blocked:
		case <-time.After(time.Second):
			t.Errorf("agent did not block new DUTs after draining")
		}
	})
	b.Stop()
	testAgentExits(t, done)
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
		StartBotFunc:      startFakeBot,
		logger:            testLogger{t},
	}
	return a, cleanup
}

// runWithDoneChannel runs the agent and returns a channel that is
// closed when the agent exits.
func runWithDoneChannel(ctx context.Context, a *Agent) <-chan struct{} {
	done := make(chan struct{})
	go func() {
		a.Run(ctx)
		close(done)
	}()
	return done
}

// testAgentExits runs a subtest testing that the agent exits using
// the channel returned from runWithDoneChannel.
func testAgentExits(t *testing.T, done <-chan struct{}) {
	t.Run("agent exits", func(t *testing.T) {
		select {
		case <-done:
		case <-time.After(time.Second):
			t.Errorf("agent did not exit")
		}
	})
}

// testLogger implements the logger interface for tests.
type testLogger struct {
	t *testing.T
}

func (t testLogger) Printf(format string, args ...interface{}) {
	// Since we loop at nanosecond interval in tests, this message
	// is very noisy.
	if format == "Reporting to queen" {
		return
	}
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

// injectStateSpyFactory creates and injects a stateSpyFactory into
// the test agent, and returns the stateSpyFactory.
func injectStateSpyFactory(a *Agent) stateSpyFactory {
	f := newStateSpyFactory()
	a.wrapStateFunc = f.wrapState
	return f
}

// injectStubClient creates and injects a stubClient into
// the test agent, and returns the stubClient.
func injectStubClient(a *Agent) *stubClient {
	c := newStubClient()
	a.Client = c
	return c
}

// injectSpyClient creates and injects a spyClient into
// the test agent, and returns the spyClient.
func injectSpyClient(a *Agent) *spyClient {
	c := newSpyClient()
	a.Client = c
	return c
}
