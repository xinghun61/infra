// Copyright 2017 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package cookflags

import (
	"fmt"

	"github.com/luci/luci-go/common/flag/flagenum"
)

// CookMode indicates the value of the -mode flag for kitchen.
type CookMode int

// Set implements flag.Value.
func (m *CookMode) Set(v string) error {
	return cookModeFlagEnum.FlagSet(m, v)
}

func (m CookMode) String() string {
	switch m {
	case CookSwarming:
		return "swarming"
	case CookBuildBot:
		return "buildbot"
	}
	return fmt.Sprintf("CookMode unknown: %d", m)
}

// These are the valid options for CookMode (with the obvious exception of the
// zero-value InvalidCookMode :)).
const (
	InvalidCookMode CookMode = iota
	CookSwarming
	CookBuildBot
)

var cookModeFlagEnum = flagenum.Enum{
	CookSwarming.String(): CookSwarming,
	CookBuildBot.String(): CookBuildBot,
}

func (m CookMode) onlyLogDog() bool {
	return m == CookSwarming
}
