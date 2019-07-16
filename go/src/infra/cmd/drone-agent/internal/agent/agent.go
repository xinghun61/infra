// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package agent implements an agent which talks to a drone queen
// service and manages Swarming bots.
package agent

import (
	"context"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"os"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/luci/common/errors"

	"infra/appengine/drone-queen/api"
	"infra/cmd/drone-agent/internal/agent/state"
	"infra/cmd/drone-agent/internal/bot"
	"infra/cmd/drone-agent/internal/draining"
)

// Agent talks to a drone queen service and manages Swarming bots.
// This struct stores the static configuration for the agent.  The
// dynamic state is stored in state.State.
type Agent struct {
	Client api.DroneClient
	// SwarmingURL is the URL of the Swarming instance.  Should be
	// a full URL without the path, e.g. https://host.example.com
	SwarmingURL string
	// WorkingDir is used for Swarming bot working dirs.  It is
	// the caller's responsibility to create this.
	WorkingDir        string
	ReportingInterval time.Duration
	DUTCapacity       int

	// logger is used for Agent logging.  If nil, use the log package.
	logger logger
	// wrapStateFunc is called to wrap the agent state.  This is
	// used for instrumenting the state for testing.  If nil, this
	// is a no-op.
	wrapStateFunc func(*state.State) stateInterface
	// startBotFunc is used to start Swarming bots.  If nil, a
	// real implementation is used.  This is set for testing.
	startBotFunc func(bot.Config) (bot.Bot, error)
}

// logger defines the logging interface used by Agent.
type logger interface {
	Printf(string, ...interface{})
}

// stateInterface is the state interface used by the agent.  The usual
// implementation of the interface is in the state package.
type stateInterface interface {
	UUID() string
	WithExpire(ctx context.Context, t time.Time) context.Context
	SetExpiration(t time.Time)
	AddDUT(dutID string)
	DrainDUT(dutID string)
	TerminateDUT(dutID string)
	DrainAll()
	TerminateAll()
	Wait()
}

// Run runs the agent until it is canceled via the context.
func (a *Agent) Run(ctx context.Context) {
	a.log("Agent starting")
	for {
		if err := a.runOnce(ctx); err != nil {
			log.Printf("Lost drone assignment: %v", err)
		}
		if draining.IsDraining(ctx) || ctx.Err() != nil {
			a.log("Agent exited")
			return
		}
	}
}

// runOnce runs one instance of registering and maintaining a drone
// assignment with the queen.
//
// If the context is canceled, this function terminates quickly and
// gracefully (e.g., like handling a SIGTERM or an abort).  If the
// context is drained, this function terminates slowly and gracefully.
// In either case, this function returns nil.
//
// If the assignment is lost or expired for whatever reason, this
// function returns an error.
func (a *Agent) runOnce(ctx context.Context) error {
	a.log("Registering with queen")
	res, err := a.Client.ReportDrone(ctx, a.reportRequest(ctx, ""))
	if err != nil {
		return errors.Annotate(err, "register with queen").Err()
	}
	if s := res.GetStatus(); s != api.ReportDroneResponse_OK {
		return errors.Reason("register with queen: got unexpected status %v", s).Err()
	}

	// Set up state.
	uuid := res.GetDroneUuid()
	if uuid == "" {
		return errors.Reason("register with queen: got empty UUID").Err()
	}
	s := a.wrapState(state.New(uuid, hook{a: a, uuid: uuid}))

	// Set up expiration context.
	t, err := ptypes.Timestamp(res.GetExpirationTime())
	if err != nil {
		return errors.Annotate(err, "register with queen: read expiration").Err()
	}
	ctx = s.WithExpire(ctx, t)

	// Do normal report update.
	if err := applyUpdateToState(res, s); err != nil {
		return errors.Annotate(err, "register with queen").Err()
	}

reportLoop:
	for {
		select {
		case <-ctx.Done():
			s.TerminateAll()
			break reportLoop
		case <-draining.C(ctx):
			s.DrainAll()
			break reportLoop
		case <-time.After(a.ReportingInterval):
		}
		a.log("Reporting to queen")
		if err := a.reportDrone(ctx, s); err != nil {
			a.log("Error reporting to queen: %s", err)
			if _, ok := err.(fatalError); ok {
				break reportLoop
			}
		}
	}
	s.Wait()
	return nil
}

// reportDrone does one cycle of calling the ReportDrone queen RPC and
// handling the response.
func (a *Agent) reportDrone(ctx context.Context, s stateInterface) error {
	res, err := a.Client.ReportDrone(ctx, a.reportRequest(ctx, s.UUID()))
	if err != nil {
		return errors.Annotate(err, "report to queen").Err()
	}
	switch rs := res.GetStatus(); rs {
	case api.ReportDroneResponse_OK:
	case api.ReportDroneResponse_UNKNOWN_UUID:
		s.TerminateAll()
		return fatalError{reason: "queen returned UNKNOWN_UUID"}
	default:
		return errors.Reason("report to queen: got unexpected status %v", rs).Err()
	}
	if err := applyUpdateToState(res, s); err != nil {
		return errors.Annotate(err, "report to queen").Err()
	}
	return nil
}

// applyUpdateToState applies the response from a ReportDrone call to the agent state.
func applyUpdateToState(res *api.ReportDroneResponse, s stateInterface) error {
	t, err := ptypes.Timestamp(res.GetExpirationTime())
	if err != nil {
		return errors.Annotate(err, "apply update to state").Err()
	}
	s.SetExpiration(t)
	draining := make(map[string]bool)
	for _, d := range res.GetDrainingDuts() {
		s.DrainDUT(d)
		draining[d] = true
	}
	for _, d := range res.GetAssignedDuts() {
		if !draining[d] {
			s.AddDUT(d)
		}
	}
	return nil
}

// reportRequest returns the api.ReportDroneRequest to use when
// reporting to the drone queen.
func (a *Agent) reportRequest(ctx context.Context, uuid string) *api.ReportDroneRequest {
	req := api.ReportDroneRequest{
		DroneUuid: uuid,
		LoadIndicators: &api.ReportDroneRequest_LoadIndicators{
			DutCapacity: intToUint32(a.DUTCapacity),
		},
	}
	if shouldRefuseNewDUTs(ctx) {
		req.LoadIndicators.DutCapacity = 0
	}
	return &req
}

// shouldRefuseNewDUTs returns true if we should refuse new DUTs.
func shouldRefuseNewDUTs(ctx context.Context) bool {
	return draining.IsDraining(ctx) || ctx.Err() != nil
}

func (a *Agent) log(format string, args ...interface{}) {
	if v := a.logger; v != nil {
		v.Printf(format, args...)
	} else {
		log.Printf(format, args...)
	}
}

func (a *Agent) wrapState(s *state.State) stateInterface {
	if a.wrapStateFunc == nil {
		return s
	}
	return a.wrapStateFunc(s)
}

func (a *Agent) startBot(c bot.Config) (bot.Bot, error) {
	if a.startBotFunc == nil {
		return bot.Start(c)
	}
	return a.startBotFunc(c)
}

// hook implements state.ControllerHook.
type hook struct {
	a    *Agent
	uuid string
}

// StartBot implements state.ControllerHook.
func (h hook) StartBot(dutID string) (bot.Bot, error) {
	dir, err := ioutil.TempDir(h.a.WorkingDir, dutID+".")
	if err != nil {
		return nil, errors.Annotate(err, "start bot %v", dutID).Err()
	}
	b, err := h.a.startBot(h.botConfig(dutID, dir))
	if err != nil {
		_ = os.RemoveAll(dir)
		return nil, errors.Annotate(err, "start bot %v", dutID).Err()
	}
	return b, nil
}

// botConfig returns a bot config for starting a Swarming bot.
func (h hook) botConfig(dutID string, workDir string) bot.Config {
	const botIDPrefix = "crossk-"
	botID := botIDPrefix + dutID
	return bot.Config{
		SwarmingURL:   h.a.SwarmingURL,
		BotID:         botID,
		WorkDirectory: workDir,
	}
}

// ReleaseDUT implements state.ControllerHook.
func (h hook) ReleaseDUT(dutID string) {
	const releaseDUTsTimeout = time.Minute
	ctx := context.Background()
	ctx, f := context.WithTimeout(ctx, releaseDUTsTimeout)
	defer f()
	req := api.ReleaseDutsRequest{
		DroneUuid: h.uuid,
		Duts:      []string{dutID},
	}
	// Releasing DUTs is best-effort.  Ignore any errors since
	// there's no way to handle them.
	//
	// TODO(ayatane): Log or track errors?
	_, _ = h.a.Client.ReleaseDuts(ctx, &req)
}

// fatalError indicates that the agent should terminate its current
// UUID assignment session and re-register with the queen.
type fatalError struct {
	reason string
}

func (e fatalError) Error() string {
	return fmt.Sprintf("agent fatal error: %s", e.reason)
}

// intToUint32 converts an int to a uint32.
// If the value is negative, return 0.
// If the value overflows, return the max value.
func intToUint32(a int) uint32 {
	if a < 0 {
		return 0
	}
	if a > math.MaxUint32 {
		return math.MaxUint32
	}
	return uint32(a)
}
