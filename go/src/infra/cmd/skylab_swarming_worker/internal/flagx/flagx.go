// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package flagx contains extra utilities to complement the flag package.
*/
package flagx

import (
	"encoding/json"
	"flag"
	"strings"

	"github.com/pkg/errors"
)

type commaList struct {
	s *[]string
}

// CommaList returns a flag.Value that can be passed to flag.Var to
// parse a comma separated list string into a string slice.
func CommaList(s *[]string) flag.Value {
	return commaList{s: s}
}

func (cl commaList) String() string {
	if cl.s == nil {
		return ""
	}
	return strings.Join(*cl.s, ",")
}

func (cl commaList) Set(s string) error {
	if cl.s == nil {
		return errors.New("CommaList pointer is nil")
	}
	*cl.s = splitCommaList(s)
	return nil
}

// splitCommaList splits a comma separated string into a slice of
// strings.  If the string is empty, return an empty slice.
func splitCommaList(s string) []string {
	if s == "" {
		return []string{}
	}
	return strings.Split(s, ",")
}

type jsonMap map[string]string

// JSONMap returns a flag.Value that can be passed to flag.Var to
// parse a JSON string into a map.
func JSONMap(m *map[string]string) flag.Value {
	return (*jsonMap)(m)
}

func (m *jsonMap) String() string {
	if m == nil {
		return "null"
	}
	d, err := json.Marshal(*m)
	if err != nil {
		// Marshaling a map[string]string shouldn't error.
		panic(err)
	}
	return string(d)
}

func (m *jsonMap) Set(s string) error {
	if m == nil {
		return errors.New("nil jsonMap pointer")
	}
	d := []byte(s)
	return json.Unmarshal(d, m)
}
