// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, cr50Converter)
	reverters = append(reverters, cr50Reverter)
}

func cr50Converter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	if v := ls.GetCr50Phase(); v != inventory.SchedulableLabels_CR50_PHASE_INVALID {
		const plen = 11 // len("CR50_PHASE_")
		lv := "cr50:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	return labels
}

func cr50Reverter(ls *inventory.SchedulableLabels, labels []string) []string {
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "cr50":
			vn := "CR50_PHASE_" + strings.ToUpper(v)
			type t = inventory.SchedulableLabels_CR50_Phase
			vals := inventory.SchedulableLabels_CR50_Phase_value
			*ls.Cr50Phase = t(vals[vn])
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
