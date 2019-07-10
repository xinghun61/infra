// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package agent

import (
	"context"
	"io/ioutil"
	"os"
	"sort"
	"sync"
	"testing"
	"time"

	"github.com/golang/protobuf/ptypes"
	"github.com/golang/protobuf/ptypes/timestamp"
	"github.com/google/go-cmp/cmp"
	"google.golang.org/grpc"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/agent/state"
	"infra/cmd/drone-agent/internal/bot"
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
		startBotFunc:      startFakeBot,
	}
	return a, cleanup
}

// startFakeBot is a fake implementation of Agent.startBotFunc.
func startFakeBot(bot.Config) (bot.Bot, error) {
	return bot.NewFakeBot(), nil
}

// stateSpyFactory implements a method that can be used as
// wrapStateFunc to inspect created states.
type stateSpyFactory struct {
	states chan *stateSpy
}

func newStateSpyFactory() stateSpyFactory {
	return stateSpyFactory{
		// These channels need to have big enough buffers to
		// capture events needed by tests.  Events that
		// overfill the channel buffers are discarded.
		states: make(chan *stateSpy, 1),
	}
}

// wrapState wraps a state in a stateSpy and sends it to waitForState.
// This method is used as wrapStateFunc.
func (f stateSpyFactory) wrapState(s *state.State) stateInterface {
	s2 := &stateSpy{
		State: s,
		// These channels need to have big enough buffers to
		// capture events needed by tests.  Events that
		// overfill the channel buffers are discarded.
		addedDUTs:     make(chan string, 8),
		drainedDUTs:   make(chan string, 8),
		terminatedAll: make(chan struct{}, 1),
		drainedAll:    make(chan struct{}, 1),
	}
	select {
	case f.states <- s2:
	default:
	}
	return s2
}

func (f stateSpyFactory) waitForState() *stateSpy {
	return <-f.states
}

// stateSpy wraps a state and allows inspecting state manipulations.
type stateSpy struct {
	*state.State
	addedDUTs     chan string
	drainedDUTs   chan string
	terminatedAll chan struct{}
	drainedAll    chan struct{}
}

func (s *stateSpy) AddDUT(dutID string) {
	s.State.AddDUT(dutID)
	select {
	case s.addedDUTs <- dutID:
	default:
	}
}

func (s *stateSpy) DrainDUT(dutID string) {
	s.State.DrainDUT(dutID)
	select {
	case s.drainedDUTs <- dutID:
	default:
	}
}

func (s *stateSpy) TerminateAll() {
	s.State.TerminateAll()
	select {
	case s.terminatedAll <- struct{}{}:
	default:
	}
}

func (s *stateSpy) DrainAll() {
	s.State.DrainAll()
	select {
	case s.drainedAll <- struct{}{}:
	default:
	}
}

// stubClient is a stub implementation of api.DroneClient.  The
// response can be modified, but writers should use withLock if
// modifying the response concurrent with other users.
type stubClient struct {
	m   sync.Mutex
	res *api.ReportDroneResponse
	err error
}

// newStubClient makes a new stubClient with sane default values.
// Tests MUST NOT rely on the exact drone UUID; the test should
// explicitly set a UUID.
func newStubClient() *stubClient {
	return &stubClient{
		res: &api.ReportDroneResponse{
			Status:         api.ReportDroneResponse_OK,
			DroneUuid:      "3679687c-b341-4422-ad6d-a935887ed6a7",
			ExpirationTime: protoTime(time.Date(9999, 1, 2, 3, 4, 5, 6, time.UTC)),
		},
	}
}

// withLock calls the function with a lock.  This is used in tests to
// modify the stubbed response.
func (c *stubClient) withLock(f func()) {
	c.m.Lock()
	f()
	c.m.Unlock()
}

func (c *stubClient) ReportDrone(ctx context.Context, req *api.ReportDroneRequest, _ ...grpc.CallOption) (*api.ReportDroneResponse, error) {
	c.m.Lock()
	defer c.m.Unlock()
	return c.res, c.err
}

func (c *stubClient) ReleaseDuts(ctx context.Context, req *api.ReleaseDutsRequest, _ ...grpc.CallOption) (*api.ReleaseDutsResponse, error) {
	return &api.ReleaseDutsResponse{}, nil
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
