// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package flagx

import (
	"strings"

	"go.chromium.org/luci/common/errors"
)

// Choice is an implementation of flag.Value for parsing a
// multiple-choice string.
type Choice struct {
	choices []string
	output  *string
}

// NewChoice creates a Choice value
func NewChoice(output *string, choices ...string) Choice {
	return Choice{choices: choices, output: output}
}

// String implements the flag.Value interface.
func (f Choice) String() string {
	if f.output == nil {
		return ""
	}
	return *f.output
}

// Set implements the flag.Value interface.
func (f Choice) Set(s string) error {
	if f.output == nil {
		return errors.Reason("Choice pointer is nil").Err()
	}
	for _, choice := range f.choices {
		if s == choice {
			*f.output = s
			return nil
		}
	}
	valid := strings.Join(f.choices, ", ")
	return errors.Reason("%s is not a valid choice; please select one of: %s", s, valid).Err()
}
