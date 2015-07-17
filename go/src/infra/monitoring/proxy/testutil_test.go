// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net/http"
	"reflect"
	"strings"
	"sync"
)

type httpError struct {
	error
	status int
}

func badRequest(err error) *httpError {
	return &httpError{err, http.StatusBadRequest}
}

func internalServerError(err error) *httpError {
	return &httpError{err, http.StatusInternalServerError}
}

func (e *httpError) Error() string {
	return e.error.Error()
}

func (e *httpError) writeError(w http.ResponseWriter) {
	http.Error(w, e.Error(), e.status)
}

type mockIgnoreType struct{}

var mockIgnore = &mockIgnoreType{}

type mockEntry struct {
	name   string
	args   []interface{}
	result []interface{}
}

func (m *mockEntry) withArgs(args ...interface{}) *mockEntry {
	return m
}

func (m *mockEntry) withResult(values ...interface{}) *mockEntry {
	m.result = values
	return m
}

func (m *mockEntry) bindResult(vars ...interface{}) {
	if len(m.result) != len(vars) {
		panic(fmt.Errorf("Result count (%d) differs from bound args (%d).", len(m.result), len(vars)))
	}

	for i, v := range vars {
		val := reflect.ValueOf(v).Elem()
		r := m.result[i]
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

func (m *mockEntry) matches(name string, args []interface{}) bool {
	if m.name != name || len(m.args) != len(args) {
		return false
	}

	for i, arg := range m.args {
		if !(arg == mockIgnore || reflect.DeepEqual(arg, args[i])) {
			return false
		}
	}
	return true
}

func (m *mockEntry) String() string {
	args := make([]string, len(m.args))
	for i, a := range m.args {
		args[i] = fmt.Sprintf("%v", a)
	}
	return fmt.Sprintf("%s(%s)", m.name, strings.Join(args, ", "))
}

type mockStruct struct {
	mocks   []*mockEntry
	mocksMu sync.Mutex
}

func (s *mockStruct) mock(name string, args ...interface{}) *mockEntry {
	entry := s.createMock(name, args)

	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()
	s.mocks = append(s.mocks, entry)
	return entry
}

func (*mockStruct) createMock(name string, args []interface{}) *mockEntry {
	return &mockEntry{
		name: name,
		args: args,
	}
}

func (s *mockStruct) pop(name string, args ...interface{}) *mockEntry {
	mock, err := s.popErr(name, args...)
	if err != nil {
		panic(err)
	}
	return mock
}

func (s *mockStruct) popErr(name string, args ...interface{}) (*mockEntry, error) {
	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()

	var (
		mockIdx int
		mock    *mockEntry
	)
	for idx, e := range s.mocks {
		if e.matches(name, args) {
			mockIdx, mock = idx, e
			break
		}
	}

	if mock == nil {
		return nil, fmt.Errorf("No mock matching %s.", s.createMock(name, args).String())
	}
	s.mocks = append(s.mocks[:mockIdx], s.mocks[mockIdx+1:]...)
	return mock, nil
}

func (s *mockStruct) remaining() []string {
	s.mocksMu.Lock()
	defer s.mocksMu.Unlock()

	remaining := []string(nil)
	for _, m := range s.mocks {
		remaining = append(remaining, m.String())
	}
	return remaining
}
