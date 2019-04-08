// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"strconv"
	"time"

	"go.chromium.org/luci/common/errors"
)

// RelativeTime is an implementation of flag.Value for parsing a time
// by a relative day offset.
type RelativeTime struct {
	T   *time.Time
	now func() time.Time
}

// String implements the flag.Value interface.
func (f RelativeTime) String() string {
	if f.T == nil {
		return "<empty>"
	}
	return f.T.Format(time.RFC1123Z)
}

// Set implements the flag.Value interface.
func (f RelativeTime) Set(s string) error {
	if f.T == nil {
		return errors.Reason("set RelativeTime: nil time pointer").Err()
	}
	n, err := strconv.Atoi(s)
	if err != nil {
		return errors.Annotate(err, "set RelativeTime").Err()
	}
	if f.now == nil {
		f.now = time.Now
	}
	*f.T = f.now().Add(time.Duration(n*24) * time.Hour)
	return nil
}
