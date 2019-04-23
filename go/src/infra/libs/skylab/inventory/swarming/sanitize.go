// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"errors"
	"fmt"
	"regexp"
)

// What is considered valid is taken from
// infra/luci/appengine/swarming/server/config.py
const (
	maxKeyLength   = 64
	maxValueLength = 256
)

var keyRegexp = regexp.MustCompile(`^[a-zA-Z_.-][0-9a-zA-Z\-\_\.]*$`)

// ReportFunc is used to report errors.
type ReportFunc func(error)

// Sanitize sanitizes the Swarming dimensions.  Invalid dimensions are
// removed or fixed as appropriate.  Errors are reported to the
// ReportFunc because there can be multiple errors and the point of
// this function is to avoid hard failures in Swarming, thus the
// common case is to log the errors somewhere.
func Sanitize(dims Dimensions, r ReportFunc) {
	for k := range dims {
		if k == "" {
			r(ErrEmptyKey)
			delete(dims, k)
			continue
		}
		if len(k) > maxKeyLength {
			r(ErrLongKey{Key: k})
			delete(dims, k)
			continue
		}
		if !keyRegexp.MatchString(k) {
			r(ErrKeyChars{Key: k})
			delete(dims, k)
			continue
		}
		sanitizeDimensionValues(dims, r, k)
	}
}

func sanitizeDimensionValues(dims Dimensions, r ReportFunc, k string) {
	vs := dims[k]
	for i := 0; i < len(vs); {
		v := vs[i]
		if v == "" {
			r(ErrEmptyValue{Key: k})
			vs = deleteValue(vs, i)
			continue
		}
		if len(v) > maxValueLength {
			r(ErrLongValue{Key: k, Value: v})
			vs = deleteValue(vs, i)
			continue
		}
		if isDupe(vs, i) {
			r(ErrRepeatedValue{Key: k, Value: v})
			vs = deleteValue(vs, i)
			continue
		}
		i++
	}
	dims[k] = vs
}

// deleteValue deletes a dimension value in place, preserving order.
func deleteValue(s []string, i int) []string {
	copy(s[i:], s[i+1:])
	return s[:len(s)-1]
}

// isDupe checks if the item at i occurs in the subslice before i.
// Dimensions should be small enough that allocating maps and hashing
// keys is much more expensive than a quick loop over a small slice.
func isDupe(s []string, i int) bool {
	for _, v := range s[:i] {
		if v == s[i] {
			return true
		}
	}
	return false
}

var (
	// ErrEmptyKey is reported by Sanitize for empty keys.
	ErrEmptyKey = errors.New("empty dimension key")
)

// ErrLongKey is reported by Sanitize for keys that are too long.
type ErrLongKey struct {
	Key string
}

func (e ErrLongKey) Error() string {
	return fmt.Sprintf("key too long: %s", e.Key)
}

// ErrKeyChars is reported by Sanitize for keys with invalid characters.
type ErrKeyChars struct {
	Key string
}

func (e ErrKeyChars) Error() string {
	return fmt.Sprintf("invalid key characters: %s", e.Key)
}

// ErrEmptyValue is reported by Sanitize for empty values.
type ErrEmptyValue struct {
	Key string
}

func (e ErrEmptyValue) Error() string {
	return fmt.Sprintf("empty value for key %s", e.Key)
}

// ErrLongValue is reported by Sanitize for values that are too long.
type ErrLongValue struct {
	Key   string
	Value string
}

func (e ErrLongValue) Error() string {
	return fmt.Sprintf("value for key %s too long: %s", e.Key, e.Value)
}

// ErrRepeatedValue is reported by Sanitize for values that are repeated.
type ErrRepeatedValue struct {
	Key   string
	Value string
}

func (e ErrRepeatedValue) Error() string {
	return fmt.Sprintf("value for key %s is repeated: %s", e.Key, e.Value)
}
