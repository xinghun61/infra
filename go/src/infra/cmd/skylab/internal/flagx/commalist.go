// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"strings"

	"go.chromium.org/luci/common/errors"
)

// CommaList is an implementation of flag.Value for parsing a comma
// separated flag argument into a string slice.
type CommaList struct {
	s *[]string
}

// NewCommaList creates a CommaList value.
func NewCommaList(s *[]string) CommaList {
	return CommaList{s: s}
}

// String implements the flag.Value interface.
func (f CommaList) String() string {
	if f.s == nil {
		return ""
	}
	return strings.Join(*f.s, ",")
}

// Set implements the flag.Value interface.
func (f CommaList) Set(s string) error {
	if f.s == nil {
		return errors.Reason("CommaList pointer is nil").Err()
	}
	*f.s = splitCommaList(s)
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
