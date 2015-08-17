// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package eventlogger provides a non-blocking logging interface for
// ChromeInfraEvents. Usage:
//
// el := eventlogger.New(context.Background(), eventlogger.Config{...})
// ctx := // ...
// evt := &cilpb.ChromeInfraEvent{...}
// el.Log(ctx,  evt)
package eventlogger

import (
	"bytes"
	"fmt"
	"infra/monitoring/messages/crit_event"
	"net/http"
	"net/http/httputil"
	"time"

	"golang.org/x/net/context"

	"github.com/golang/protobuf/proto"
	"github.com/luci/luci-go/common/clock"
	"github.com/luci/luci-go/common/logging"
)

const (
	maxEvts = 1024
	// TraceID is the context.Context Value key for trace IDs. If present
	// on contexts passed to Log, it will be set on the logged event proto.
	TraceID = "chrome-infra-trace-id"
)

// Config encapsulates event logging configration parameters.
type Config struct {
	// Endpoint is the destination URL for log events.
	Endpoint      string
	Hostname      string
	Service       string
	AppengineName string
	Interval      time.Duration
	Client        *http.Client
}

// EventLogger sends ChromeInfraEvents to a logging destination.
type EventLogger interface {
	// Log logs evt asynchronously and returns immediately. Will
	// panic if called after Start() returns.
	Log(ctx context.Context, evt *crit_event.ChromeInfraEvent)
}

type evtLogger struct {
	cfg Config
	// This is really just a cached convenience message.
	src   *crit_event.InfraEventSource
	evtCh chan *crit_event.LogRequestLite_LogEventLite
	// TODO: trace ID etc.
}

// New returns a new EventLogger. If cfg.Interval is not set,
// it will be assigned time.Second as the default. cfg.Client
// will likewise be asinged http.DefaultClient by default.
func New(ctx context.Context, cfg Config) EventLogger {
	if cfg.Interval == time.Duration(0) {
		cfg.Interval = time.Second
	}
	if cfg.Client == nil {
		cfg.Client = http.DefaultClient
	}

	ret := &evtLogger{
		cfg:   cfg,
		evtCh: make(chan *crit_event.LogRequestLite_LogEventLite, maxEvts),
		src: &crit_event.InfraEventSource{
			HostName:      proto.String(cfg.Hostname),
			AppengineName: proto.String(cfg.AppengineName),
			ServiceName:   proto.String(cfg.Service),
		},
	}

	go func() {
		if err := ret.start(ctx); err != nil {
			logging.Errorf(ctx, "Error: %v", err)
		}
	}()

	return ret
}

// Start runs the event flushing loop. It does not return until either
// an error occurs or ctx.Done().
func (l *evtLogger) start(ctx context.Context) error {
	defer close(l.evtCh)

	evtBuf := []*crit_event.LogRequestLite_LogEventLite{}
	clck := clock.Get(ctx)

	flush := func(evts []*crit_event.LogRequestLite_LogEventLite) error {
		// TODO: Auth, retry/backoff etc.
		req := &crit_event.LogRequestLite{
			RequestTimeMs: proto.Int64(clck.Now().Unix()),
			LogSourceName: proto.String("CHROME_INFRA"),
			LogEvent:      evts,
		}

		logging.Infof(ctx, "Flushing %v events\n", len(req.LogEvent))

		b, err := proto.Marshal(req)
		if err != nil {
			return err
		}

		resp, err := l.cfg.Client.Post(l.cfg.Endpoint, "application/octet-stream", bytes.NewBuffer(b))
		if err != nil {
			return err
		}

		defer resp.Body.Close()
		if resp.StatusCode >= 400 {
			b, err := httputil.DumpResponse(resp, true)
			logging.Errorf(ctx, "Error body: %v %v", string(b), err)
			return fmt.Errorf("http status %d: %s", resp.StatusCode, l.cfg.Endpoint)
		}

		return nil
	}

	// Loop:
	// - If you can read an event off ch, append it to the array of events.
	// - If you can't read an event off ch, and it's been at least 1s since the
	// last flush call, then flush the events if there are any buffered up.
	// - if ctx.Done() returns something, try one last flush and exit.

	// Ways this can act poorly:
	// - If the capacity of l.evtCh is full and a client attempts to log an event,
	// that client will block.  This is unlikely to happen because the select
	// statement spends very little time on anything else, including the flush
	// operation.
	// - If flush operations take longer than the flushTicker delay, then
	// multiple simultaneous flush operations can stack up.
	// - If flush operation fail, there is no retry mechanism (yet) and they
	// will just log an error locally.
	ticker := clck.After(l.cfg.Interval)
	for {
		select {
		case evt := <-l.evtCh:
			evtBuf = append(evtBuf, evt)
		case <-ticker:
			if len(evtBuf) > 0 {
				// Flush in a separate goroutine so we can free this
				// one up to keep reading off of l.evtCh and not block
				// clients.  TODO(seanmccullough): add retry logic on
				// POST failure, but make sure to not leak memory. This
				// may mean dropping events or persisting them to disk.
				go func(evts []*crit_event.LogRequestLite_LogEventLite) {
					if err := flush(evts); err != nil {
						logging.Errorf(ctx, "Error flushing: %v", err.Error())
					}
				}(evtBuf)
				// The above goroutine has a copy of evtBuf, so
				// we can now reset it safely.
				evtBuf = []*crit_event.LogRequestLite_LogEventLite{}
			}
			ticker = clck.After(time.Second)
		case <-ctx.Done():
			if len(evtBuf) > 0 {
				if err := flush(evtBuf); err != nil {
					logging.Errorf(ctx, "Error flushing: %v", err.Error())
				}
			}
			logging.Infof(ctx, "Event logger exiting.")
			return nil
		}
	}
}

func (l *evtLogger) Log(ctx context.Context, evt *crit_event.ChromeInfraEvent) {
	// Get this as soon as possible, so proto encoding time etc
	// doesn't bump the logged event time.
	clck := clock.Get(ctx)
	now := clck.Now().Unix()

	evt.EventSource = l.src
	// TODO: Consider making this a func parameter.
	evt.TimestampKind = crit_event.ChromeInfraEvent_POINT.Enum()

	if trace, ok := ctx.Value(TraceID).(string); ok {
		evt.TraceId = proto.String(trace)
	}

	// TODO:
	//	evt.SpanId = // ?
	//	evt.ParentId = // ?

	bytes, err := proto.Marshal(evt)
	if err != nil {
		logging.Errorf(ctx, "Error marshaling ChromeInfraEvent: %v", err.Error())
		return
	}

	l.evtCh <- &crit_event.LogRequestLite_LogEventLite{
		EventTimeMs:     proto.Int64(now),
		EventCode:       proto.Int32(0),
		EventFlowId:     proto.Int32(0),
		SourceExtension: bytes,
	}
}
