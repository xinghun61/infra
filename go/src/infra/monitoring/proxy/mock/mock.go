// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package mock

import (
	"fmt"
	"reflect"
	"strings"
	"sync"
)

type httpError struct {
	error
	status int
}

type mockIgnoreType struct{}

// Ignore is a sentinel value that can be supplied as a mock argument to
// instruct the mock system not to assert that parameter's value .
var Ignore = &mockIgnoreType{}

// Call is a single recorded mocked call, complete with expected arguments and
// return values.
type Call struct {
	parent *Mock
	name   string
	args   []interface{}
	result []interface{}
}

// WithResult adds positional return value parameters to the mock.
func (c *Call) WithResult(values ...interface{}) *Call {
	c.result = values
	return c
}

// BindResult takes pointers to positional return values and copies the mocked
// return value expectations into them.
func (c *Call) BindResult(vars ...interface{}) {
	if len(c.result) != len(vars) {
		c.parent.AddError(fmt.Errorf("Result count (%d) differs from bound args (%d).", len(c.result), len(vars)))
		return
	}

	for i, v := range vars {
		val := reflect.ValueOf(v).Elem()
		r := c.result[i]
		switch val.Kind() {
		case reflect.Bool:
			val.SetBool(r.(bool))

		case reflect.Interface, reflect.Slice:
			if r == nil || reflect.ValueOf(r).IsNil() {
				val.Set(reflect.Zero(val.Type()))
			} else {
				val.Set(reflect.ValueOf(r))
			}

		default:
			panic(fmt.Sprintf("Don't know how to handle kind %s.", val.Kind()))
		}
	}
}

func (c *Call) matches(name string, args []interface{}) bool {
	if c.name != name || len(c.args) != len(args) {
		return false
	}

	for i, arg := range c.args {
		if !(arg == Ignore || reflect.DeepEqual(arg, args[i])) {
			return false
		}
	}
	return true
}

func (c *Call) String() string {
	args := make([]string, len(c.args))
	for i, a := range c.args {
		args[i] = fmt.Sprintf("%v", a)
	}
	return fmt.Sprintf("%s(%s)", c.name, strings.Join(args, ", "))
}

// Mocked implements GetMock, which returns a pointer to the object's Mock
// structure.
type Mocked interface {
	GetMock() *Mock
}

// Mock can be embedded into a struct to give it access to the mock subsystem
// and its accounting.
type Mock struct {
	mocks   []*Call
	mocksMu sync.Mutex
	errors  []error
}

var _ Mocked = (*Mock)(nil)

// GetMock implements the Mocked interface.
func (s *Mock) GetMock() *Mock {
	return s
}

// MockCall creates a Call with the supplied function name and arguments. It
// returns the Call object, which can then have its result values (if any) added
// via WithResult.
func (s *Mock) MockCall(name string, args ...interface{}) *Call {
	call := s.createCall(name, args)

	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()
	s.mocks = append(s.mocks, call)
	return call
}

func (s *Mock) createCall(name string, args []interface{}) *Call {
	return &Call{
		parent: s,
		name:   name,
		args:   args,
	}
}

// Pop pops a matching mock call from the call list, adding an error to the mock
// if it is not registered.
func (s *Mock) Pop(name string, args ...interface{}) *Call {
	mock, err := s.PopErr(name, args...)
	if err != nil {
		s.AddError(err)
	}
	return mock
}

// PopErr pops a matching mock call from the call list, returning an error if
// it is not registered.
func (s *Mock) PopErr(name string, args ...interface{}) (*Call, error) {
	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()

	var (
		mockIdx int
		mock    *Call
	)
	for idx, e := range s.mocks {
		if e.matches(name, args) {
			mockIdx, mock = idx, e
			break
		}
	}

	if mock == nil {
		mock = s.createCall(name, args)
		return mock, fmt.Errorf("No registered mock matching %s.", s.createCall(name, args).String())
	}
	s.mocks = append(s.mocks[:mockIdx], s.mocks[mockIdx+1:]...)
	return mock, nil
}

// AddError adds an error to the mock's error list.
func (s *Mock) AddError(err error) {
	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()

	s.errors = append(s.errors, err)
}

// ShouldHaveNoErrors tests the exit criteria for a mock. It asserts that
// there are no errors during mock usage and that there are no registered mock
// calls that haven't been called.
func ShouldHaveNoErrors(actual interface{}, expected ...interface{}) string {
	s := actual.(Mocked).GetMock()

	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()

	problems := []string{}
	for _, err := range s.errors {
		problems = append(problems, fmt.Sprintf("Error during mock: %v", err))
	}
	for _, r := range s.mocks {
		problems = append(problems, fmt.Sprintf("Unused mock was registered: %v", r))
	}
	return strings.Join(problems, "\n")
}
