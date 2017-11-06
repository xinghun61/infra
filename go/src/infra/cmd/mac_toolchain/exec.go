// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"
	"os"
	"os/exec"
	"strings"

	"golang.org/x/net/context"
)

// Cmd abstracts exec.Cmd into a mockable interface for testing.
type Cmd interface {
	Output() ([]byte, error)
	Run() error
	SetStdin(io.Reader)
	SetStdout(*os.File)
	SetStderr(*os.File)
}

// Session abstracts exec.CommandContext into a mockable interface for testing.
type Session interface {
	CommandContext(ctx context.Context, executable string, args ...string) Cmd
}

// RealCmd wraps exec.Cmd to implement Cmd.
type RealCmd struct {
	exec.Cmd
}

var _ Cmd = &RealCmd{}

// SetStdin implements Cmd.
func (c *RealCmd) SetStdin(r io.Reader) {
	c.Stdin = r
}

// SetStdout implements Cmd.
func (c *RealCmd) SetStdout(f *os.File) {
	c.Stdout = f
}

// SetStderr implements Cmd.
func (c *RealCmd) SetStderr(f *os.File) {
	c.Stderr = f
}

// RealSession wraps exec.CommandContext to implement Session.
type RealSession struct{}

var _ Session = &RealSession{}

// CommandContext implements Session.
func (s *RealSession) CommandContext(ctx context.Context, executable string, args ...string) Cmd {
	var c RealCmd
	c.Cmd = *exec.CommandContext(ctx, executable, args...)
	return &c
}

type sessionKeyType string

const sessionKey sessionKeyType = "cmdKey"

func useRealExec(ctx context.Context) context.Context {
	return context.WithValue(ctx, sessionKey, &RealSession{})
}

// CommandContext pulls a mockable version of exec.CommandContext from ctx.
func CommandContext(ctx context.Context, executable string, args ...string) Cmd {
	s, ok := ctx.Value(sessionKey).(Session)
	if !ok {
		s = &RealSession{}
	}
	return s.CommandContext(ctx, executable, args...)
}

// RunCommand runs `executable` and passes its stderr/stdout through.
func RunCommand(ctx context.Context, executable string, args ...string) error {

	cmd := CommandContext(ctx, executable, args...)
	cmd.SetStdout(os.Stdout)
	cmd.SetStderr(os.Stderr)
	return cmd.Run()
}

// RunWithStdin runs `executable`, passes `stdin` as an input stream, and passes
// stderr/stdout through.
func RunWithStdin(ctx context.Context, stdin string, executable string, args ...string) error {
	cmd := CommandContext(ctx, executable, args...)
	cmd.SetStdout(os.Stdout)
	cmd.SetStderr(os.Stderr)
	cmd.SetStdin(strings.NewReader(stdin))
	return cmd.Run()
}

// RunOutput runs `executable` and collects its output.
func RunOutput(ctx context.Context, executable string, args ...string) (out string, err error) {
	bytes, err := CommandContext(ctx, executable, args...).Output()
	if err != nil {
		return
	}
	out = string(bytes)
	return
}
