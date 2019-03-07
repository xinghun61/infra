// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, cr50Converter)
}

func cr50Converter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	if v := ls.GetCr50Phase(); v != inventory.SchedulableLabels_CR50_PHASE_INVALID {
		dims["label-cr50_phase"] = []string{v.String()}
	}
}
