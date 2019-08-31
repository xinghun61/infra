// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, cr50Converter)
	reverters = append(reverters, cr50Reverter)
}

func cr50Converter(dims Dimensions, ls *inventory.SchedulableLabels) {
	if v := ls.GetCr50Phase(); v != inventory.SchedulableLabels_CR50_PHASE_INVALID {
		dims["label-cr50_phase"] = []string{v.String()}
	}
}

func cr50Reverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	if v, ok := getLastStringValue(d, "label-cr50_phase"); ok {
		if cr50, ok := inventory.SchedulableLabels_CR50_Phase_value[v]; ok {
			*ls.Cr50Phase = inventory.SchedulableLabels_CR50_Phase(cr50)
		}
		delete(d, "label-cr50_phase")
	}
	return d
}
