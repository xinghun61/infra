// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, basicConverter)
}

func basicConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	if v := ls.GetBoard(); v != "" {
		lv := "board:" + v
		labels = append(labels, lv)
	}
	if v := ls.GetModel(); v != "" {
		lv := "model:" + v
		labels = append(labels, lv)
	}
	if v := ls.GetPlatform(); v != "" {
		lv := "platform:" + v
		labels = append(labels, lv)
	}
	switch v := ls.GetEcType(); v {
	case inventory.SchedulableLabels_EC_TYPE_CHROME_OS:
		labels = append(labels, "ec:cros")
	}
	if v := ls.GetOsType(); v != inventory.SchedulableLabels_OS_TYPE_INVALID {
		const plen = 8 // len("OS_TYPE_")
		lv := "os:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	if v := ls.GetPhase(); v != inventory.SchedulableLabels_PHASE_INVALID {
		const plen = 6 // len("PHASE_")
		lv := "phase:" + v.String()[plen:]
		labels = append(labels, lv)
	}
	for _, v := range ls.GetVariant() {
		lv := "variant:" + v
		labels = append(labels, lv)
	}
	return labels
}
