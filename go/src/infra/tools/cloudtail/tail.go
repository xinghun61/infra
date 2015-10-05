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

	"github.com/luci/luci-go/common/logging"
	"gopkg.in/fsnotify.v1"

	"infra/tools/cloudtail/internal"
)

// See corresponding fields of TailerOptions.
const (
	DefaultRotationCheckPeriod = 5 * time.Second
	DefaultPollingPeriod       = 500 * time.Millisecond
	DefaultReadBufferLen       = 1024 * 64
)

// TailerOptions is passed to NewTailer.
type TailerOptions struct {
	// Path identifies a file to watch.
	Path string

	// PushBuffer knows how to forward log entries to the client.
	PushBuffer PushBuffer

	// Parser converts text lines into log entries, default is StdParser().
	Parser LogParser

	// Logger is used for local tailer own log messages.
	Logger logging.Logger

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
	stopping chan struct{} // closed when Stop is called
	stopped  chan struct{} // closed when internal goroutine has finished
}

// NewTailer spawn a goroutine that watches a file for changes and pushes
// new lines to the buffer.
func NewTailer(opts TailerOptions) (*Tailer, error) {
	var err error
	opts.Path, err = filepath.Abs(opts.Path)
	if err != nil {
		return nil, err
	}
	if opts.Parser == nil {
		opts.Parser = StdParser()
	}
	if opts.Logger == nil {
		opts.Logger = logging.Null()
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

	tailer := &Tailer{
		stopping: make(chan struct{}),
		stopped:  make(chan struct{}),
	}

	// Wakes up on file change notifications. Closes after 'stopping' is closed
	// and all pending notifications are sent.
	var changeSignal chan checkType
	if !opts.UsePolling {
		var err error
		changeSignal, err = signalOnChanges(opts.Path, opts.Logger, opts.PollingPeriod, tailer.stopping)
		if err != nil {
			opts.Logger.Warningf("Failed to initialize fsnotify, polling instead: %s", err)
		}
	}
	if changeSignal == nil {
		changeSignal = signalPeriodically(opts.PollingPeriod, tailer.stopping)
	}

	// poller.Poll() -> source -> PushBuffer (in drainChannel).
	source := make(chan string)
	go func() {
		defer close(source)
		defer close(tailer.stopped)

		poller := filePoller{path: opts.Path}
		poller.Init(opts.SeekToEnd, opts.ReadBufferLen)
		defer poller.Close()
		if opts.initializedSignal != nil {
			close(opts.initializedSignal)
		}

		lastCheck := time.Time{}
		forceCheck := true

		for {
			// Do os.Stat scan after each wakeup timeout (forceCheck == true) or at
			// least each RotationCheckPeriod.
			now := time.Now()
			checkExistence := forceCheck || now.Sub(lastCheck) > opts.RotationCheckPeriod
			if checkExistence {
				lastCheck = now
			}
			forceCheck = false

			// Read new lines, push them downstream (via 'source' channel).
			err := poller.Poll(checkExistence, source, tailer.stopping)
			if err != nil && !os.IsNotExist(err) {
				opts.Logger.Errorf("tail error: %s", err)
			}

			// Wake up periodically to make os.Stat check to detect file truncation.
			wakeupIn := lastCheck.Add(opts.RotationCheckPeriod).Sub(time.Now())
			if wakeupIn < 0 {
				wakeupIn = 0
			}

			// Wait for wakeup timer or for incoming change notification.
			// changeSignal is closed when the watcher goroutine exits (happens when
			// tailer.stopping is closed, i.e. when Stop() is called).
			select {
			case <-time.After(wakeupIn):
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
	go drainChannel(source, opts.Parser, opts.PushBuffer, opts.Logger)

	return tailer, nil
}

// Stop asynchronously notifies tailer to stop. Panics if called twice.
func (t *Tailer) Stop() error {
	close(t.stopping)
	return nil
}

// Wait waits for the tailer to be in stopped state (i.e. no more messages
// will be pushed to the buffer). There still can be unsent messages in-flight
// in PushBuffer though.
func (t *Tailer) Wait() error {
	<-t.stopped
	return nil
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
func (p *filePoller) Init(seekToEnd bool, readBufferLen int) {
	p.buf = make([]byte, readBufferLen)

	// Ignore errors here (e.g. file is missing). They are discovered and
	// reported in 'Poll'. The polling loop is more smart with respect to error
	// handling.
	if p.reopen() == nil && seekToEnd {
		offset, err := p.file.Seek(0, os.SEEK_END)
		if err == nil {
			p.offset = offset
		}
	}
}

// Poll reads all new lines since last call to Poll and pushes them to 'sink'.
func (p *filePoller) Poll(checkExistence bool, sink chan string, stop chan struct{}) error {
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
				p.readLines(sink, stop)
				if len(p.incompleteLine) != 0 {
					sink <- string(p.incompleteLine)
				}
				p.reset()
			}
		}
	}

	if p.file == nil {
		if err := p.reopen(); err != nil {
			return err
		}
	}
	p.readLines(sink, stop)
	return nil
}

func (p *filePoller) Close() {
	p.reset()
}

func (p *filePoller) reopen() error {
	if p.file != nil {
		return fmt.Errorf("file is already open")
	}
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

func (p *filePoller) readLines(sink chan string, stop chan struct{}) {
	// Read as much as possible. Check 'stop' signal only before reading next
	// block: that way we don't have to deal with read but unparsed data later.
	// It assumes len(p.buf) is relatively small (so outer 'for' loop spins
	// relatively fast).
loop:
	for {
		select {
		case <-stop:
			break loop
		default:
		}

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
				sink <- string(newLine)
			} else {
				p.incompleteLine = append(p.incompleteLine, newLine...)
				sink <- string(p.incompleteLine)
				p.incompleteLine = nil
			}
		}

		if err != nil {
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
// 'interval' milliseconds. Can be used for dumb polling of the file state.
// Returned channel closes when 'done' channel is closed.
func signalPeriodically(interval time.Duration, done chan struct{}) chan checkType {
	out := make(chan checkType)
	go func() {
		defer close(out)
		for {
			select {
			case <-done:
				return
			case <-time.After(interval):
				out <- normalCheck
			}
		}
	}()
	return out
}

// signalOnChanges returns a channel that receives some checkType whenever
// file specified by 'path' changes. Caller must be prepared for false events,
// for the file being unexpectedly missing and all other conditions.
// Consider 'signalOnChanges' to be a smart version of 'signalPeriodically' that
// Returned channel closes when 'done' channel is closed.
func signalOnChanges(path string, logger logging.Logger, interval time.Duration, done chan struct{}) (chan checkType, error) {
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
				logger.Debugf(msg)
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
				}
			}
			var timeout <-chan time.Time
			if !added {
				timeout = time.After(interval)
			}

			select {
			case <-done:
				return
			case <-timeout:
				out <- statCheck
			case err := <-watcher.Errors:
				watcher.Remove(path)
				added = false
				spamLog("fsnotify: unexpected error - %s, polling", err)
			case ev := <-watcher.Events:
				if ev.Op == fsnotify.Rename || ev.Op == fsnotify.Remove {
					added = false
					spamLog("fsnotify: file is gone, polling")
					out <- statCheck
				} else {
					out <- normalCheck
				}
			}
		}
	}()

	return out, nil
}
