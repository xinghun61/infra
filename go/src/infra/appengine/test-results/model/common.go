// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package model

import (
	"bytes"
	"strconv"
)

// Node is a node in a Tests tree.
//
// In reality, it as almost as weak as empty interface,
// but the unexported method allow the package to achieve
// type safety internally.
type Node interface {
	node()
}

// Number is an integer that supports JSON unmarshaling from a string
// and marshaling back to a string.
type Number int

// UnmarshalJSON unmarshals data into n.
// data is expected to be a JSON string. If the string
// fails to parse to an integer, UnmarshalJSON returns
// an error.
func (n *Number) UnmarshalJSON(data []byte) error {
	data = bytes.Trim(data, `"`)
	// swarmed webkit_layout_tests (possibly others) apparently use this value.
	// It only causes problems when trying to parse *un*merged test results
	// directly from isolate.
	if string(data) == "DUMMY_BUILD_NUMBER" {
		return nil
	}

	num, err := strconv.Atoi(string(data))
	if err != nil {
		return err
	}
	*n = Number(num)
	return nil
}

// MarshalJSON marshals n into JSON string.
func (n *Number) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Itoa(int(*n))), nil
}
