// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package atutil provides a higher level Autotest interface than the autotest package.
*/
package atutil

import (
	"context"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/pkg/errors"

	"infra/cros/cmd/phosphorus/internal/autotest"
	"infra/cros/cmd/phosphorus/internal/osutil"
)

const (
	keyvalFile      = "keyval"
	autoservPidFile = ".autoserv_execute"
	tkoPidFile      = ".parser_execute"
)

// RunAutoserv runs an autoserv task.
//
// This function always returns a non-nil Result, but some fields may
// not be meaningful.  For example, Result.Exit will be 0 even if
// autoserv could not be run.  In this case, Result.Started will be
// false and an error will also returned.
//
// Output is written to the Writer.
//
// Result.TestsFailed may not be set, depending on AutoservJob.  An
// error is not returned for test failures.
func RunAutoserv(ctx context.Context, m *MainJob, j AutoservJob, w io.Writer) (r *Result, err error) {
	if m.UseLocalHostInfo {
		if err2 := prepareHostInfo(m.ResultsDir, j); err2 != nil {
			return nil, err2
		}
		defer func() {
			if err2 := retrieveHostInfo(m.ResultsDir, j); err2 != nil {
				log.Printf("Failed to retrieve host info for autoserv test: %s", err2)
				if err == nil {
					err = err2
				}
			}
		}()
	}
	a := j.AutoservArgs()
	if j, ok := j.(keyvalsJob); ok {
		if err := writeKeyvals(a.ResultsDir, j.JobKeyvals()); err != nil {
			return &Result{}, err
		}
	}
	switch {
	case isTest(a):
		return runTest(ctx, m.AutotestConfig, a, w)
	default:
		return runTask(ctx, m.AutotestConfig, a, w)
	}
}

// TKOParse runs tko/parse on the results directory.  The level is
// used by tko/parse to determine how many parts of the results dir
// absolute path to take for the unique job tag.
//
// Parse output is written to the Writer.
//
// This function returns the number of tests failed and an error if
// any.
func TKOParse(c autotest.Config, resultsDir string, level int, w io.Writer) (failed int, err error) {
	a := &autotest.ParseArgs{
		Level:          level,
		RecordDuration: true,
		Reparse:        true,
		ResultsDir:     resultsDir,
		SingleDir:      true,
		SuiteReport:    true,
		WritePidfile:   true,
	}
	cmd := autotest.ParseCommand(c, a)
	cmd.Stdout = w
	cmd.Stderr = w
	if err := cmd.Run(); err != nil {
		return 0, errors.Wrap(err, "run tko/parse")
	}
	p := filepath.Join(resultsDir, tkoPidFile)
	n, err := readTestsFailed(p)
	if err != nil {
		return 0, errors.Wrap(err, "parse tests failed")
	}
	return n, nil
}

// runTask runs an autoserv task.
//
// Result.TestsFailed is always zero.
func runTask(ctx context.Context, c autotest.Config, a *autotest.AutoservArgs, w io.Writer) (*Result, error) {
	r := &Result{}
	cmd := autotest.AutoservCommand(c, a)
	cmd.Stdout = w
	cmd.Stderr = w

	var err error
	r.RunResult, err = osutil.RunWithAbort(ctx, cmd)
	if err != nil {
		return r, err
	}
	if es, ok := cmd.ProcessState.Sys().(syscall.WaitStatus); ok {
		r.Exit = es.ExitStatus()
	} else {
		return r, errors.New("RunAutoserv: failed to get exit status: unknown process state")
	}
	if r.Exit != 0 {
		return r, errors.Errorf("RunAutoserv: exited %d", r.Exit)
	}
	return r, nil
}

// runTest runs an autoserv test.
//
// Unlike runTask, this function performs some things only needed for
// tests, like parsing the number of test failed and writing a job
// finished timestamp.
func runTest(ctx context.Context, c autotest.Config, a *autotest.AutoservArgs, w io.Writer) (*Result, error) {
	r, err := runTask(ctx, c, a, w)
	if !r.Started {
		return r, err
	}
	p := filepath.Join(a.ResultsDir, autoservPidFile)
	if i, err2 := readTestsFailed(p); err2 != nil {
		if err == nil {
			err = err2
		}
	} else {
		r.TestsFailed = i
	}
	if err2 := appendJobFinished(a.ResultsDir); err == nil {
		err = err2
	}
	return r, err
}

// isTest returns true if the given AutoservArgs represents a test
// job.
func isTest(a *autotest.AutoservArgs) bool {
	switch {
	case a.Verify, a.Cleanup, a.Reset, a.Repair, a.Provision:
		return false
	default:
		return true
	}
}

// readTestsFailed reads the number of tests failed from the given
// pid file.
func readTestsFailed(pidFile string) (int, error) {
	b, err := ioutil.ReadFile(pidFile)
	if err != nil {
		return 0, err
	}
	s := string(b)
	lines := strings.Split(s, "\n")
	if len(lines) < 3 {
		return 0, fmt.Errorf("Not enough lines in pidfile %s", pidFile)
	}
	i, err := strconv.Atoi(lines[2])
	if err != nil {
		return 0, err
	}
	return i, nil
}

func writeKeyvals(resultsDir string, m map[string]string) error {
	p := keyvalPath(resultsDir)
	if err := os.MkdirAll(filepath.Dir(p), 0777); err != nil {
		return err
	}
	f, err := os.OpenFile(p, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0666)
	if err != nil {
		return err
	}
	defer f.Close()
	err = autotest.WriteKeyvals(f, m)
	if err2 := f.Close(); err == nil {
		err = err2
	}
	return err
}

// appendJobFinished appends a job_finished value to the test’s keyval file.
func appendJobFinished(resultsDir string) error {
	p := keyvalPath(resultsDir)
	msg := fmt.Sprintf("job_finished=%d\n", time.Now().Unix())
	return appendToFile(p, msg)
}

func keyvalPath(resultsDir string) string {
	return filepath.Join(resultsDir, keyvalFile)
}
