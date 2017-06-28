// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bufio"
	"bytes"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/golang/protobuf/proto"
	"golang.org/x/net/context"

	"infra/tools/git/state"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/retry"
	"github.com/luci/luci-go/common/retry/transient"
	"github.com/luci/luci-go/common/system/environ"
	"github.com/luci/luci-go/common/system/exitcode"
	"github.com/luci/luci-go/common/system/filesystem"
)

// GitRunnerMode determines how a GitRunner should be run.
type GitRunnerMode int

// GitCommand describes an exec.Cmd-like interface to a Git command.
type GitCommand struct {
	// State (required) is the current execution state of the Git wrapper.
	//
	// The State's "GitPath" is the path of the Git command to run.
	State state.State

	// LowSpeedLimit, if >0, sets the low speed limit (in bytes) for the Git
	// process. If Git receives fewer than this many bytes per second, it is
	// considered to be in "low speed".
	//
	// See GIT_HTTP_LOW_SPEED_LIMIT environment variable for more information.
	LowSpeedLimit int

	// LowSpeedTime, if >0, sets the low speed time for the Git process. If Git
	// is in "low speed" for more than this amount of time, it will fail.
	//
	// See GIT_HTTP_LOW_SPEED_TIME environment variable for more information.
	LowSpeedTime time.Duration

	// RetryList is a list of per-line regular expressions to run on Git output.
	// If any of these expressions is encountered, the Git execution will be
	// considered transient, and it will re-execute on non-zero return code.
	RetryList []*regexp.Regexp

	// WorkDir is the working directory to use for Git. If this is the empty
	// string, the application's working directory will be used.
	WorkDir string

	// Stdin will be used as the STDIN pipe for the Git process. If nil, os.Stdin
	// will be used.
	Stdin io.Reader

	// Stdout will receive the Git process' STDOUT. If nil, STDOUT will be
	// directed to os.Stdout.
	Stdout io.Writer

	// Stderr will receive the Git process' STDERR. If nil, STDERR will be
	// directed to os.Stdout.
	Stderr io.Writer

	// Retry is the retry Factory to use for retries. If nil, no retries will be
	// performed.
	Retry retry.Factory

	// testOnStart (testing), if not nil, is a callback that will be called after
	// the Start() command has been successfully executed against a process.
	testOnStart func()

	// testParseSkipArgs (testing) is the number of arguments to skip when parsing
	// the Git command-line. This is used to ignore the arguments prepended by the
	// Git test harness.
	testParseSkipArgs int
}

// Run executes the configured Git command. On success, it will return the
// return code from Git and a nil error. On failure, it will return an error
// describing that failure.
func (gc *GitCommand) Run(c context.Context, args []string, env environ.Env) (int, error) {
	gitArgs := ParseGitArgs(args[gc.testParseSkipArgs:]...)

	// Determine our working directory. If we find it, resolve it to an absolute
	// path. Otherwise, store it as an empty string.
	effectiveWorkDir := gitArgs.Base().WorkDir(gc.WorkDir)
	if effectiveWorkDir == "" {
		// Use system working directory.
		var err error
		if effectiveWorkDir, err = os.Getwd(); err != nil {
			logging.Warningf(c, "Couldn't determine effective working directory: %s", err)
		}
	}
	if effectiveWorkDir != "" {
		// Make working directory absolute, if possible.
		if err := filesystem.AbsPath(&effectiveWorkDir); err != nil {
			logging.Warningf(c, "Couldn't get absolute path of effective working directory [%s]: %s",
				effectiveWorkDir, err)
		}
	}

	// Clone our environment, so we can modify it.
	gr := gitRunner{
		GitCommand: gc,
		Args:       args,
		Env:        env.Clone(),
		WorkDir:    gc.WorkDir,
	}

	if l := gc.LowSpeedLimit; l > 0 {
		gr.Env.Set("GIT_HTTP_LOW_SPEED_LIMIT", strconv.Itoa(l))
	}
	if l := gc.LowSpeedTime; l > 0 {
		secs := int(l.Seconds())
		if secs <= 0 {
			// Handle rounding error.
			secs = 1
		}
		gr.Env.Set("GIT_HTTP_LOW_SPEED_TIME", strconv.Itoa(secs))
	}

	// Determine if we are running a retry-able subcommand.
	st := proto.Clone(&gc.State).(*state.State)
	if gitArgs.MayBeRemote() {
		// If we're already running through a retry wrapper, always run the Git
		// command directly, rather than wrapping it multiple times. Otherwise,
		// configure our runner for retries.
		st.Retrying = !st.Retrying
	}

	gr.Env.Set(gitWrapperENV, st.ToENV())

	// Execute our Git command.
	switch {
	case gitArgs.IsVersion():
		// Special case: if our Git subcommand is "version", tack on some
		// information about this wrapper.
		return gr.runGitVersion(c)

	case st.Retrying:
		// If we're retrying the "clone" subcommand, we may need to do some
		// directory management. If "clone" starts, then transiently fails, it will
		// have created its destination directory. This will prevent future "clone"
		// calls from succeeding, since the directory now already exists.
		//
		// To mitigate this, we will identify the "clone" target directory. If it
		// doesn't exist, we'll delete it in between retries.
		if gca, ok := gitArgs.(*GitCloneArgs); ok {
			if tdir := gca.TargetDir(); tdir != "" && effectiveWorkDir != "" {
				if !filepath.IsAbs(tdir) {
					tdir = filepath.Join(effectiveWorkDir, tdir)
				}
				if _, err := os.Stat(tdir); os.IsNotExist(err) {
					// We're doing a clone, and the target directory does not exist. If
					// it is created during operation, we assume ownership of it in
					// between retries.
					gr.BetweenRetryFunc = gc.removeCloneDirBetweenRetries(tdir)
				}
			}
		}

		return gr.runWithRetries(c)

	default:
		return gr.runDirect(c)
	}
}

// removeCloneDirBetweenRetries returns a betweenRetryFunc that is bound to
// the clone directory. It will recursively remove the directory if it exists
// in between retries so that a half-failed clone doesn't break subsequent
// clone attempts.
func (gc *GitCommand) removeCloneDirBetweenRetries(cloneDir string) betweenRetryFunc {
	return func(c context.Context) error {
		if st, err := os.Stat(cloneDir); err == nil && st.IsDir() {
			logging.Infof(c, "Cleaning up `clone` target directory for retry: %s", cloneDir)
			if err := filesystem.RemoveAll(cloneDir); err != nil {
				return errors.Annotate(err).Reason("failed to remove 'clone' directory in between retries").
					D("cloneDir", cloneDir).
					Err()
			}
		}
		return nil
	}
}

// betweenRetryFunc is a callback that is invoked in between Git retries.
type betweenRetryFunc func(context.Context) error

// gitRunner is a configured Git execution.
type gitRunner struct {
	*GitCommand

	// Args is the arguments to pass to Git.
	Args []string

	// Env is the environemnt to use for the Git subcommand. Env may be modified
	// during execution.
	Env environ.Env

	// WorkDir is the working directory to use.
	WorkDir string

	// BetweenRetryFunc, if not nil, is an optional function that gets executed in
	// between retries. If it returns an error, subsequent retry attempts will be
	// abandoned.
	BetweenRetryFunc betweenRetryFunc

	// For tests, allows mocking runtime.GOOS. If empty, uses real runtime.GOOS
	// value.
	testGOOS string
}

func (gr *gitRunner) getStdin() io.Reader {
	if gr.Stdin != nil {
		return gr.Stdin
	}
	return os.Stdin
}

func (gr *gitRunner) getStdout() io.Writer {
	if gr.Stdout != nil {
		return gr.Stdout
	}
	return os.Stdout
}

func (gr *gitRunner) getStderr() io.Writer {
	if gr.Stderr != nil {
		return gr.Stderr
	}
	return os.Stderr
}

func (gr *gitRunner) runWithRetries(c context.Context) (int, error) {
	var rc int
	transientFailures := 0

	c, cancelFunc := context.WithCancel(c)
	defer cancelFunc()

	var brfErr error
	err := retry.Retry(c, transient.Only(gr.Retry), func() (err error) {
		var trigger Trigger

		makeMonitor := func() *Monitor {
			return &Monitor{
				Expressions: gr.RetryList,
				Trigger:     &trigger,
			}
		}
		stdoutPM := makeMonitor()
		stderrPM := makeMonitor()

		if rc, err = gr.runOnce(c, stdoutPM, stderrPM); err != nil {
			// Hard failure.
			return err
		}

		if rc != 0 {
			// Did we hit a transient error?
			trans := false
			if s := stdoutPM.Found; s != "" {
				logging.Warningf(c, "Transient error string identified in STDOUT: %q", s)
				trans = true
			}
			if s := stderrPM.Found; s != "" {
				logging.Warningf(c, "Transient error string identified in STDERR: %q", s)
				trans = true
			}

			if trans {
				return errors.New("transient error string encountered", transient.Tag)
			}
		}

		return nil
	}, func(err error, delay time.Duration) {
		logging.Warningf(c, "Retrying after %s (rc=%d): %s", delay, rc, err)
		transientFailures++

		if brf := gr.BetweenRetryFunc; brf != nil {
			if brfErr = brf(c); brfErr != nil {
				// Prevent future retries.
				logging.Errorf(c, "Failed to recover in between retries: %s", err)
				cancelFunc()
			}
		}
	})

	switch {
	case err != nil && !transient.Tag.In(err):
		// Hard failure.
		return 0, err

	case brfErr != nil:
		return 0, brfErr

	default:
		// Success or transient failure; propagate the last return code.
		if transientFailures > 0 {
			logging.Warningf(c, "Command completed with rc %d after %d transient failure(s).", rc, transientFailures)
		}
		return rc, nil
	}
}

// goos returns either the mocked os version, or the real runtime.GOOS.
func (gr *gitRunner) goos() string {
	if gr.testGOOS == "" {
		return runtime.GOOS
	}
	return gr.testGOOS
}

func (gr *gitRunner) setupCommand(c context.Context) *exec.Cmd {
	args := gr.Args
	if gr.goos() == "windows" && strings.HasSuffix(strings.ToLower(gr.State.GitPath), ".bat") {
		// If the 'real' git we're invoking is a .bat file, we need to escape
		// ^ characters twice:
		//   * once when the .bat processes its own cmdline args
		//   * again when the .bat invokes the underlying git.exe
		args = make([]string, len(gr.Args))
		for i := range gr.Args {
			args[i] = strings.Replace(gr.Args[i], "^", "^^^^", -1)
		}
	}

	cmd := exec.CommandContext(c, gr.State.GitPath, args...)
	cmd.Env = gr.Env.Sorted()
	cmd.Stdin = gr.getStdin()
	cmd.Dir = gr.WorkDir

	return cmd
}

func (gr *gitRunner) runOnce(c context.Context, stdoutPM, stderrPM *Monitor) (int, error) {
	// Create internal cancellation function in case something goes wrong at
	// runtime.
	c, cancelFunc := context.WithCancel(c)
	defer cancelFunc()

	cmd := gr.setupCommand(c)

	var wg sync.WaitGroup
	pipeErrs := make(errors.MultiError, 0, 2)
	linkMonitor := func(m *Monitor, fn func() (io.ReadCloser, error), out io.Writer) (func(), error) {

		pipe, err := fn()
		if err != nil {
			return nil, errors.Annotate(err).Reason("failed to create pipe").Err()
		}

		r := io.Reader(pipe)
		if out != nil {
			r = io.TeeReader(r, out)
		}

		// Augment our "pipeErrs" error slice, and retain our error index.
		errIdx := len(pipeErrs)
		pipeErrs = append(pipeErrs, nil)

		return func() {
			wg.Add(1)
			go func() {
				defer wg.Done()

				if err := m.Consume(r); err != nil {
					pipeErrs[errIdx] = err
					cancelFunc()
				}
			}()
		}, nil
	}

	stdoutFn, err := linkMonitor(stdoutPM, cmd.StdoutPipe, gr.getStdout())
	if err != nil {
		return 0, errors.Annotate(err).Reason("failed to create STDOUT pipe").Err()
	}

	stderrFn, err := linkMonitor(stderrPM, cmd.StderrPipe, gr.getStderr())
	if err != nil {
		return 0, errors.Annotate(err).Reason("failed to create STDERR pipe").Err()
	}

	if err := cmd.Start(); err != nil {
		return 0, errors.Annotate(err).Reason("failed to start process").Err()
	}

	// Begin our monitor goroutines.
	stdoutFn()
	stderrFn()

	// (Testing) notify test harness that the process has started.
	if gr.testOnStart != nil {
		gr.testOnStart()
	}

	// Wait for our I/O to complete. This will terminate when our pipes have
	// closed, so we don't need to close them after this (double-close).
	wg.Wait()

	// Wait for our process to finish.
	if err := cmd.Wait(); err != nil {
		if rc, ok := exitcode.Get(err); ok {
			return rc, nil
		}
		return 0, errors.Annotate(err).Reason("failed to complete process").Err()
	}

	// If our pipes hit any errors, propagate them.
	if err := pipeErrs.First(); err != nil {
		return 0, pipeErrs
	}

	// Success!
	return 0, nil
}

func (gr *gitRunner) runGitVersion(c context.Context) (int, error) {
	var stdout, stderr bytes.Buffer

	cmd := gr.setupCommand(c)
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	// Run the sub-command.
	err := cmd.Run()

	// If the command executed successfully, post-process STDOUT.
	if err == nil {
		wrapperSuffix := (" / Infra wrapper (" + versionString + ")")

		// We are expecting STDOUT to be a single line of text.
		if nidx := bytes.IndexRune(stdout.Bytes(), '\n'); nidx > 0 {
			var nbuf bytes.Buffer
			nbuf.Grow(stdout.Len() + len(wrapperSuffix))
			_, _ = nbuf.Write(stdout.Bytes()[:nidx])
			_, _ = nbuf.WriteString(wrapperSuffix)
			_, _ = nbuf.Write(stdout.Bytes()[nidx:])
			stdout = nbuf
		}
	}

	// Write any STDOUT or STDERR data that it produced, in that order.
	writeBuf := func(b *bytes.Buffer, out io.Writer, name string) {
		if b.Len() > 0 && out != nil {
			if _, err := b.WriteTo(out); err != nil {
				logging.Warningf(c, "Failed to write %s content: %s", name, err)
			}
		}
	}
	writeBuf(&stdout, gr.getStdout(), "STDOUT")
	writeBuf(&stderr, gr.getStderr(), "STDERR")

	if rc, ok := exitcode.Get(err); ok {
		return rc, nil
	}
	return 0, errors.Annotate(err).Reason("failed to execute process").Err()
}

func (gr *gitRunner) runDirect(c context.Context) (int, error) {
	cmd := gr.setupCommand(c)
	cmd.Stdout = gr.getStdout()
	cmd.Stderr = gr.getStderr()

	err := cmd.Run()
	if rc, ok := exitcode.Get(err); ok {
		return rc, nil
	}
	return 0, errors.Annotate(err).Reason("failed to execute process").Err()
}

// Monitor continuously monitors a Reader for expression lines. If one is
// encountered, or if an error is encountered, it will mark this state.
type Monitor struct {
	// Expressions is the set of per-line regular expressions to scan for.
	Expressions []*regexp.Regexp

	// Found will non-empty set to the line that matched an expression, if a match
	// is identified.
	Found string

	// Trigger is a shared trigger between Monitors. It allows one Monitor to
	// notify other Monitors that an expression has been found, enabling them to
	// stop wasting time scanning for one.
	//
	// If nil, no state sharing will occur.
	Trigger *Trigger
}

// Consume reads r and processes it line-by-line until it hits io.EOF. If
// expressions are encountered during processing, the first will be recorded
// in the Monitor's Found field.
//
// If io.EOF is encountered, Consume will return with a nil error return code.
// Otherwise, if an error is encountered, Consume will stop reading and return
// that error.
func (m *Monitor) Consume(r io.Reader) error {
	br := bufio.NewReader(r)

	// If we have regular expressions, read line-by-line and run each through the
	// full set of expressions. We will stop if our stream has ended (EOF), if we
	// encounter a regex hit, or if we are notified externally via trigger that
	// a regex hit has been found elsewhere.
	eof := false
	if len(m.Expressions) > 0 {
		for !eof && m.Found == "" {
			if m.Trigger.Triggered() {
				// Fall back to fast path for the remainder of this stream.
				break
			}

			line, err := br.ReadString('\n')
			switch err {
			case nil: // Do nothing.
			case io.EOF:
				eof = true
			default:
				return errors.Annotate(err).Reason("failed to process stream").Err()
			}

			// Don't process empty lines. Likewise, if we were triggered during the
			// read, there's no point in running this line through the regex list.
			if line == "" || m.Trigger.Triggered() {
				continue
			}
			for _, re := range m.Expressions {
				if re.MatchString(line) {
					m.Trigger.Trigger()
					m.Found = line
					break
				}
			}
		}
	}

	// If we did not hit EOF, we still need to consume the remainder of the
	// Reader as part of our contract. Read from it in batches and dump it to
	// the void, since we don't actually need to process it.
	if !eof {
		if _, err := io.Copy(devNull{}, r); err != nil {
			return errors.Annotate(err).Reason("failed to consume stream remainder").Err()
		}
	}
	return nil
}

type devNull struct{}

func (dn devNull) Write(b []byte) (int, error) { return len(b), nil }

// Trigger is a shared boolean object.
//
// A nil Trigger is valid, and can never be triggered.
type Trigger struct {
	value int32
}

// Triggered returns true if this Trigger has been triggered.
func (t *Trigger) Triggered() bool {
	if t == nil {
		return false
	}
	return atomic.LoadInt32(&t.value) > 0
}

// Trigger sets the Triggered state to true.
func (t *Trigger) Trigger() {
	if t != nil {
		atomic.AddInt32(&t.value, 1)
	}
}
