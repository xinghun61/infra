// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package registry

import (
	"fmt"
	"regexp"
	"strings"
)

var validTagRe = regexp.MustCompile(`^[a-zA-Z0-9_\.\-]+$`)

// ValidateTag checks syntax of a docker tag.
//
// A tag name must be valid ASCII and may contain lowercase and uppercase
// letters, digits, underscores, periods and dashes. A tag name may not start
// with a period or a dash and may contain a maximum of 128 characters.
func ValidateTag(t string) error {
	switch {
	case t == "":
		return fmt.Errorf("bad docker tag %q: can't be empty", t)
	case strings.HasPrefix(t, "."):
		return fmt.Errorf("bad docker tag %q: can't start with '.'", t)
	case strings.HasPrefix(t, "-"):
		return fmt.Errorf("bad docker tag %q: can't start with '-'", t)
	case len(t) > 128:
		return fmt.Errorf("bad docker tag %q: can't have more than 128 characters", t)
	case !validTagRe.MatchString(t):
		return fmt.Errorf("bad docker tag %q: should match %s", t, validTagRe)
	default:
		return nil
	}
}
