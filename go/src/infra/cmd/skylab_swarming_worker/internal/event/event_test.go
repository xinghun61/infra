// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// +build darwin linux

package event

import (
	"os/exec"
	"strings"
	"testing"
)

// call captures a call to a handler function made by Handle().  This
// function is used for testing.
type call struct {
	e Event
	m string
}

func sameCalls(a, b []call) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// Test that sameCalls works for happy path and edge cases.
func TestSameCalls(t *testing.T) {
	type testcase struct {
		a []call
		b []call
	}
	for _, x := range []testcase{
		{[]call{}, []call{}},
		{[]call{{"foo", "bar"}}, []call{{"foo", "bar"}}},
	} {
		if !sameCalls(x.a, x.b) {
			t.Errorf("%v and %v did not compare equal", x.a, x.b)
		}
	}
	for _, x := range []testcase{
		{[]call{{"foo", "bar"}}, []call{}},
		{[]call{{"foo", "bar"}}, []call{{"foo", "bar"}, {"spam", "eggs"}}},
	} {
		if sameCalls(x.a, x.b) {
			t.Errorf("%v and %v compared equal", x.a, x.b)
		}
	}
}

const testInput = `foo
foo bar
foo bar baz
`

// Test that Handle calls the provided handler with each event and message.
func TestHandle(t *testing.T) {
	r := strings.NewReader(testInput)
	calls := make([]call, 0, 3)
	f := func(e Event, m string) {
		calls = append(calls, call{e, m})
	}
	err := Handle(r, f)
	expected := []call{
		{"foo", ""},
		{"foo", "bar"},
		{"foo", "bar baz"},
	}
	if !sameCalls(calls, expected) {
		t.Errorf("Unexpected calls, expected %v, got %v", expected, calls)
	}
	if err != nil {
		t.Errorf("Handle returned an error: %s", err)
	}
}

// Test that RunCommand runs a command and calls the provided handler correctly.
func TestRunCommand(t *testing.T) {
	c := exec.Command("echo", "-n", testInput)
	calls := make([]call, 0, 3)
	f := func(e Event, m string) {
		calls = append(calls, call{e, m})
	}
	err := RunCommand(c, f)
	expected := []call{
		{"foo", ""},
		{"foo", "bar"},
		{"foo", "bar baz"},
	}
	if !sameCalls(calls, expected) {
		t.Errorf("Unexpected calls, got %v, expected %v", calls, expected)
	}
	if err != nil {
		t.Errorf("RunCommand returned an error: %s", err)
	}
}
