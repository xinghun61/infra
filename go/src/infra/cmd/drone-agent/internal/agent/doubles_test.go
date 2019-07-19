// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package agent

import (
	"context"
	"sync"
	"time"

	"google.golang.org/grpc"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/agent/state"
	"infra/cmd/drone-agent/internal/bot"
)

// newPersistentBot returns a FakeBot that does not exit when
// drained/terminated.  The Stop method must be called to explicitly
// stop the bot.
func newPersistentBot() *bot.FakeBot {
	b := bot.NewFakeBot()
	b.DrainFunc = func(*bot.FakeBot) error { return nil }
	b.TerminateFunc = func(*bot.FakeBot) error { return nil }
	return b
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

// wrapState wraps a state in a stateSpy and sends it to the channel.
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

var endOfTime = protoTime(time.Date(9999, 1, 2, 3, 4, 5, 6, time.UTC))

// newStubClient makes a new stubClient with sane default values.
// Tests MUST NOT rely on the exact drone UUID; the test should
// explicitly set a UUID.
func newStubClient() *stubClient {
	return &stubClient{
		res: &api.ReportDroneResponse{
			Status:         api.ReportDroneResponse_OK,
			DroneUuid:      "3679687c-b341-4422-ad6d-a935887ed6a7",
			ExpirationTime: endOfTime,
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
	// Make a copy to prevent concurrent access.
	res := *c.res
	return &res, c.err
}

func (c *stubClient) ReleaseDuts(ctx context.Context, req *api.ReleaseDutsRequest, _ ...grpc.CallOption) (*api.ReleaseDutsResponse, error) {
	return &api.ReleaseDutsResponse{}, nil
}

type spyClient struct {
	*stubClient
	reports chan *api.ReportDroneRequest
}

func newSpyClient() *spyClient {
	return &spyClient{
		stubClient: newStubClient(),
		// These channels need to have big enough buffers to
		// capture events needed by tests.  Events that
		// overfill the channel buffers are discarded.
		reports: make(chan *api.ReportDroneRequest, 2),
	}
}

func (c *spyClient) ReportDrone(ctx context.Context, req *api.ReportDroneRequest, o ...grpc.CallOption) (*api.ReportDroneResponse, error) {
	select {
	case c.reports <- req:
	default:
	}
	return c.stubClient.ReportDrone(ctx, req, o...)
}
