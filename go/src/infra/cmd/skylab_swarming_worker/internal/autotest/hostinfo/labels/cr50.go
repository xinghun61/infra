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
