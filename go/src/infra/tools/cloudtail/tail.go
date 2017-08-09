// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cloudtail

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"golang.org/x/net/context"
	"gopkg.in/fsnotify.v1"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"

	"infra/tools/cloudtail/internal"
)

// See corresponding fields of TailerOptions.
const (
	DefaultRotationCheckPeriod = 5 * time.Second
	DefaultPollingPeriod       = 500 * time.Millisecond
	DefaultReadBufferLen       = 1024 * 256
)

// TailerOptions is passed to NewTailer.
type TailerOptions struct {
	// Path identifies a file to watch.
	Path string

	// PushBuffer knows how to forward log entries to the client.
	PushBuffer PushBuffer

	// Parser converts text lines into log entries, default is StdParser().
	Parser LogParser

	// SeekToEnd is true to seek to file's end before tailing.
	SeekToEnd bool

	// UsePolling is true to disable fsnotify watchers and use polling.
	UsePolling bool

	// RotationCheckPeriod defines how often to call os.Stat to see whether
	// the file has been moved or truncated.
	RotationCheckPeriod time.Duration

	// PollingPeriod defines how often to poll file for changes if fsnotify system
	// is not working.
	PollingPeriod time.Duration

	// ReadBufferLen is maximum number of bytes read from file in one operation.
	ReadBufferLen int

	// initializedSignal is used for synchronization in unit tests. It is closed
	// after poller has initialized it's state and starts polling.
	initializedSignal chan struct{}
}

// Tailer watches a file for changes and pushes new lines to a the buffer.
type Tailer struct {
	opts     TailerOptions
	stopping chan struct{} // closed when Stop is called
}

// NewTailer prepares a Tailer.
//
// Use its 'Run' method to start tailing a file.
func NewTailer(opts TailerOptions) (*Tailer, error) {
	var err error
	opts.Path, err = filepath.Abs(opts.Path)
	if err != nil {
		return nil, err
	}
	if opts.Parser == nil {
		opts.Parser = StdParser()
	}
	if opts.RotationCheckPeriod == 0 {
		opts.RotationCheckPeriod = DefaultRotationCheckPeriod
	}
	if opts.PollingPeriod == 0 {
		opts.PollingPeriod = DefaultPollingPeriod
	}
	if opts.ReadBufferLen == 0 {
		opts.ReadBufferLen = DefaultReadBufferLen
	}

	return &Tailer{
		opts:     opts,
		stopping: make(chan struct{}),
	}, nil
}

// Run watches a file for changes and pushes new lines to the buffer.
//
// Use Stop() (from another goroutine) to gracefully terminate the tailer, or
// cancel the context to abort it ASAP.
func (tailer *Tailer) Run(ctx context.Context) {
	// The inner context is canceled when tailer.Stop is called. It aborts all
	// tailer guts, but doesn't stop 'drainChannel' (so all pending data still can
	// be sent).
	innerCtx, abort := context.WithCancel(ctx)
	go func() {
		select {
		case <-tailer.stopping:
			abort()
		case <-innerCtx.Done(): // to avoid leaking this goroutine
		}
	}()
	defer abort() // this would kill the goroutine above for sure

	// Wakes up on file change notifications. Closes after innerCtx is closed
	// and all pending notifications are sent.
	var changeSignal chan checkType
	if !tailer.opts.UsePolling {
		var err error
		changeSignal, err = signalOnChanges(innerCtx, tailer.opts.Path, tailer.opts.PollingPeriod)
		if err != nil {
			logging.Warningf(innerCtx, "Failed to initialize fsnotify, polling instead: %s", err)
		}
	}
	if changeSignal == nil {
		changeSignal = signalPeriodically(innerCtx, tailer.opts.PollingPeriod)
	}

	// poller.Poll() -> source -> PushBuffer (in drainChannel).
	source := make(chan string)
	go func() {
		defer close(source)

		poller := filePoller{path: tailer.opts.Path}
		poller.Init(ctx, tailer.opts.SeekToEnd, tailer.opts.ReadBufferLen)
		defer poller.Close()
		if tailer.opts.initializedSignal != nil {
			close(tailer.opts.initializedSignal)
		}

		lastCheck := time.Time{}
		forceCheck := true

		// The final poll is happening with the outer context. So if inner context
		// is canceled (e.g. on Stop), we are still able to send stuff (to terminate
		// gracefully). If outer context is canceled too, 'Poll' does nothing.
		defer func() {
			logging.Debugf(ctx, "Doing the final tailer poll...")
			poller.Poll(ctx, false, source)
		}()

		for {
			// Do os.Stat scan after each wakeup timeout (forceCheck == true) or at
			// least each RotationCheckPeriod.
			now := clock.Now(innerCtx)
			checkExistence := forceCheck || now.Sub(lastCheck) > tailer.opts.RotationCheckPeriod
			if checkExistence {
				lastCheck = now
			}
			forceCheck = false

			// Read new lines, push them downstream (via 'source' channel).
			err := poller.Poll(innerCtx, checkExistence, source)
			if err != nil && !os.IsNotExist(err) {
				logging.Errorf(innerCtx, "tail error: %s", err)
			}

			// Wake up periodically to make os.Stat check to detect file truncation.
			wakeupIn := lastCheck.Add(tailer.opts.RotationCheckPeriod).Sub(clock.Now(innerCtx))
			if wakeupIn < 0 {
				wakeupIn = 0
			}

			// Wait for wakeup timer or for incoming change notification.
			// changeSignal is closed when the watcher goroutine exits (happens when
			// tailer.stopping is closed, i.e. when Stop() is called).
			select {
			case res := <-clock.After(innerCtx, wakeupIn):
				if res.Err != nil {
					return // the context was canceled
				}
				forceCheck = true
			case check, alive := <-changeSignal:
				if !alive {
					return
				}
				forceCheck = check == statCheck
			}

			// Drain all pending change notifications, no need to run Poll() multiple
			// times in a row.
			drained := false
			for !drained {
				select {
				case check, alive := <-changeSignal:
					if !alive {
						return
					}
					if check == statCheck {
						forceCheck = true
					}
				default:
					drained = true
				}
			}
		}
	}()

	// Note: canceled context here would cause all logs from 'source' to be simply
	// dropped.
	drainChannel(ctx, source, tailer.opts.Parser, tailer.opts.PushBuffer)
}

// Stop asynchronously notifies tailer to stop (i.e. 'Run' to unblock and
// return). Panics if called twice.
func (tailer *Tailer) Stop() {
	close(tailer.stopping)
}

/// File state poller.

// filePoller knows how to read changes made to a file between two 'Poll' calls.
// It can detect file appearing and disappearing, file rotation and truncation.
// Used from single goroutine only.
type filePoller struct {
	path string

	file           *os.File    // non nil if currently tailing some file
	stat           os.FileInfo // used for os.SameFile call to detect rotation
	offset         int64       // position of the file pointer
	incompleteLine []byte      // last unfinished line of the file

	buf []byte // temporary space to avoid reallocating it all the time
}

// Init prepares poller for operations.
func (p *filePoller) Init(ctx context.Context, seekToEnd bool, readBufferLen int) {
	p.buf = make([]byte, readBufferLen)

	// Ignore errors here (e.g. file is missing). They are discovered and
	// reported in 'Poll'. The polling loop is more smart with respect to error
	// handling.
	if p.reopen(ctx) == nil && seekToEnd {
		offset, err := p.file.Seek(0, os.SEEK_END)
		if err == nil {
			p.offset = offset
		}
	}
}

// Poll reads all new lines since last call to Poll and pushes them to 'sink'.
//
// Exits ASAP if the context is canceled.
func (p *filePoller) Poll(ctx context.Context, checkExistence bool, sink chan string) error {
	// Slow code path (doing extra os.Stat) if there's suspicion the file has
	// been moved.
	if checkExistence {
		exists := true
		stat, err := os.Stat(p.path)
		if err != nil {
			// Treat permission errors as if file doesn't exist.
			if !os.IsNotExist(err) && !os.IsPermission(err) {
				return err
			}
			exists = false
		}

		// Was missing and still missing? Do nothing.
		if p.file == nil && !exists {
			return os.ErrNotExist
		}

		// Suddenly deleted, rotated, moved or truncated? Read what we can from
		// still open file handle and close it. New one is reopened below.
		if p.file != nil {
			if !exists || !os.SameFile(p.stat, stat) || stat.Size() < p.offset {
				p.readLines(ctx, sink)
				if len(p.incompleteLine) != 0 {
					select {
					case sink <- string(p.incompleteLine):
					case <-ctx.Done():
					}
				}
				p.reset()
			}
		}
	}

	if p.file == nil {
		if err := p.reopen(ctx); err != nil {
			return err
		}
	}
	p.readLines(ctx, sink)
	return nil
}

func (p *filePoller) Close() {
	p.reset()
}

func (p *filePoller) reopen(ctx context.Context) error {
	if p.file != nil {
		return fmt.Errorf("file is already open")
	}
	logging.Debugf(ctx, "Opening the file for tailing: %s", p.path)
	f, err := internal.OpenForSharedRead(p.path)
	if err != nil {
		return err
	}
	stat, err := f.Stat()
	if err != nil {
		f.Close()
		return err
	}
	p.file = f
	p.stat = stat
	p.offset = 0
	p.incompleteLine = nil
	return nil
}

func (p *filePoller) reset() {
	if p.file != nil {
		p.file.Close()
		p.file = nil
	}
	p.stat = nil
	p.offset = 0
	p.incompleteLine = nil
}

func (p *filePoller) readLines(ctx context.Context, sink chan string) {
	for {
		size, err := p.file.Read(p.buf)
		p.offset += int64(size)

		// Read() can read something and return error at the same time. So parse
		// output regardless of err value.
		buf := p.buf[:size]
		for len(buf) > 0 {
			idx := bytes.IndexByte(buf, '\n')
			if idx == -1 {
				p.incompleteLine = append(p.incompleteLine, buf...)
				break
			}
			newLine := buf[:idx]
			buf = buf[idx+1:] // skip '\n' itself
			// Avoid uselessly copying newLine into new buffer.
			if p.incompleteLine == nil {
				select {
				case sink <- string(newLine):
				case <-ctx.Done():
				}
			} else {
				p.incompleteLine = append(p.incompleteLine, newLine...)
				select {
				case sink <- string(p.incompleteLine):
				case <-ctx.Done():
				}
				p.incompleteLine = nil
			}
		}

		if err != nil {
			return // usually EOF
		}

		// Canceled?
		if ctx.Err() != nil {
			return
		}
	}
}

/// File change watchers.

type checkType int

const (
	// normalCheck is returned to instruct poller to attempt to read file.
	normalCheck checkType = iota

	// statCheck is returned to instruct poller to os.Stat and read the file.
	// Watcher returns it when there's suspicion tailed file has been moved or
	// truncated or when it doesn't exist.
	statCheck
)

// signalPeriodically returns a channel that receives normalCheck value each
// 'interval' milliseconds.
//
// Can be used for dumb polling of the file state.
//
// Returned channel closes when the context is canceled.
func signalPeriodically(ctx context.Context, interval time.Duration) chan checkType {
	out := make(chan checkType)
	go func() {
		defer close(out)
		for {
			select {
			case res := <-clock.After(ctx, interval):
				if res.Err != nil {
					return // context closed
				}
				out <- normalCheck
			}
		}
	}()
	return out
}

// signalOnChanges returns a channel that receives some checkType whenever
// file specified by 'path' changes.
//
// Caller must be prepared for false events, for the file being unexpectedly
// missing and all other conditions. Consider 'signalOnChanges' to be a smart
// version of 'signalPeriodically'.
//
// The returned channel closes when the context is closed.
func signalOnChanges(ctx context.Context, path string, interval time.Duration) (chan checkType, error) {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, err
	}

	out := make(chan checkType)

	go func() {
		defer close(out)
		defer watcher.Close()

		lastLogMsg := ""
		spamLog := func(f string, args ...interface{}) {
			msg := fmt.Sprintf(f, args...)
			if lastLogMsg != msg {
				logging.Debugf(ctx, msg)
				lastLogMsg = msg
			}
		}

		added := false
		for {
			// A watcher can be placed only on existing file. So until 'path' is
			// successfully added to watcher, use polling.
			if !added {
				if err := watcher.Add(path); err != nil {
					spamLog("fsnotify: failed to add watcher - %s, polling", err)
				} else {
					added = true
					logging.Debugf(ctx, "Added file system watch: %s", path)
				}
			}
			var timeout <-chan clock.TimerResult
			if !added {
				timeout = clock.After(ctx, interval)
			}

			select {
			case <-ctx.Done():
				return
			case res := <-timeout:
				if res.Err != nil {
					return // the context was canceled
				}
				out <- statCheck
			case err := <-watcher.Errors:
				watcher.Remove(path)
				added = false
				spamLog("fsnotify: unexpected error - %s, polling", err)
			case ev := <-watcher.Events:
				if ev.Op == fsnotify.Rename || ev.Op == fsnotify.Remove {
					added = false
					logging.Debugf(ctx, "The file is gone, removing the watch: %s", ev)
					watcher.Remove(path)
					out <- statCheck
				} else {
					out <- normalCheck
				}
			}
		}
	}()

	return out, nil
}
