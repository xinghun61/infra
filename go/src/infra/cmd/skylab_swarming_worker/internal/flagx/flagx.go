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

	"go.chromium.org/luci/common/errors"
)

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
		return errors.Reason("JSONMap pointer is nil").Err()
	}
	d := []byte(s)
	return json.Unmarshal(d, m)
}
