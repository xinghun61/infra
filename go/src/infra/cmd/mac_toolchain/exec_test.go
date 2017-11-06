// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"
	"io/ioutil"
	"os"
	"testing"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/errors"

	. "github.com/smartystreets/goconvey/convey"
)

// MockSession mocks a series of command invocations.
type MockSession struct {
	Calls        []*MockCmd // Records command invocations
	ReturnError  []error    // Errors to return by commands (default: nil)
	ReturnOutput []string   // Stdout to return by commands (default: "")
}

// MockCmd mocks a single command invocation.
type MockCmd struct {
	Stdin      io.Reader // Saved Stdin to be read by Run()
	Executable string    // The name of the command
	Args       []string  // Command line arguments of the command

	ReturnError   error  // Error to be returned by the invocation
	ReturnOutput  string // Stdout to be return by the invocation
	ConsumedStdin string // Result of reading Stdin (for reading in tests)
}

var _ Cmd = &MockCmd{}

// SetStdin implements Cmd.
func (c *MockCmd) SetStdin(r io.Reader) {
	c.Stdin = r
}

// SetStdout implements Cmd.
func (c *MockCmd) SetStdout(f *os.File) {
}

// SetStderr implements Cmd.
func (c *MockCmd) SetStderr(f *os.File) {
}

// CommandContext implements Session.
func (s *MockSession) CommandContext(_ context.Context, executable string, args ...string) Cmd {
	c := &MockCmd{Executable: executable, Args: args}
	if len(s.ReturnError) > len(s.Calls) {
		c.ReturnError = s.ReturnError[len(s.Calls)]
	}
	if len(s.ReturnOutput) > len(s.Calls) {
		c.ReturnOutput = s.ReturnOutput[len(s.Calls)]
	}
	s.Calls = append(s.Calls, c)
	return c
}

func (c *MockCmd) Run() error {
	if c.Stdin != nil {
		data, err := ioutil.ReadAll(c.Stdin)
		if err != nil {
			return err
		}
		c.ConsumedStdin = string(data)
	}
	return c.ReturnError
}

func (c *MockCmd) Output() ([]byte, error) {
	if err := c.Run(); err != nil {
		return nil, err
	}
	return []byte(c.ReturnOutput), nil
}

func useMockCmd(ctx context.Context, s *MockSession) context.Context {
	return context.WithValue(ctx, sessionKey, s)
}

func TestExec(t *testing.T) {
	t.Parallel()

	Convey("External command execution works", t, func() {
		var s MockSession
		ctx := useMockCmd(context.Background(), &s)

		Convey("CommandContext uses RealCmd by default", func() {
			_, ok := CommandContext(context.Background(), "test-exe", "arg1", "arg2").(*RealCmd)
			So(ok, ShouldBeTrue)
		})

		Convey("CommandContext works", func() {
			cmd, ok := CommandContext(ctx, "test-exe", "arg1", "arg2").(*MockCmd)
			So(ok, ShouldBeTrue)
			So(cmd.Executable, ShouldEqual, "test-exe")
			So(cmd.Args, ShouldResemble, []string{"arg1", "arg2"})
		})

		Convey("RunCommand works for succeeding command", func() {
			err := RunCommand(ctx, "test-run", "arg")
			So(err, ShouldBeNil)
			So(s.Calls[0].Executable, ShouldEqual, "test-run")
			So(s.Calls[0].Args, ShouldResemble, []string{"arg"})
		})

		Convey("RunCommand works for failing command", func() {
			s.ReturnError = []error{errors.Reason("test error").Err()}
			err := RunCommand(ctx, "bad-cmd")
			So(err, ShouldNotBeNil)
		})

		Convey("RunWithStdin works", func() {
			err := RunWithStdin(ctx, "test input", "test-exec")
			So(err, ShouldBeNil)
			So(s.Calls[0].ConsumedStdin, ShouldEqual, "test input")
			So(s.Calls[0].Executable, ShouldEqual, "test-exec")
			So(s.Calls[0].Args, ShouldResemble, []string(nil))
		})

		Convey("RunOutput works", func() {
			s.ReturnOutput = []string{"test output 1", "out2"}
			out, err := RunOutput(ctx, "cmd1", "b1", "b2")
			So(err, ShouldBeNil)
			So(out, ShouldEqual, "test output 1")

			out, err = RunOutput(ctx, "cmd2", "c1", "c2")
			So(err, ShouldBeNil)
			So(out, ShouldEqual, "out2")

			So(s.Calls[0].Executable, ShouldEqual, "cmd1")
			So(s.Calls[1].Executable, ShouldEqual, "cmd2")

			So(s.Calls[0].Args, ShouldResemble, []string{"b1", "b2"})
			So(s.Calls[1].Args, ShouldResemble, []string{"c1", "c2"})
		})

		Convey("RunOutput works for failing command", func() {
			s.ReturnError = []error{errors.Reason("test error").Err()}
			s.ReturnOutput = []string{"test output"}
			_, err := RunOutput(ctx, "output-cmd", "b1", "b2")
			So(err, ShouldNotBeNil)
		})
	})
}
