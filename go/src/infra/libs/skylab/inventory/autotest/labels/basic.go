// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	reverters = append(reverters, basicReverter)
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
	if v := ls.GetReferenceDesign(); v != "" {
		lv := "reference_design:" + v
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

func basicReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "board":
			*ls.Board = v
		case "model":
			*ls.Model = v
		case "platform":
			*ls.Platform = v
		case "ec":
			switch v {
			case "cros":
				*ls.EcType = inventory.SchedulableLabels_EC_TYPE_CHROME_OS
			default:
				continue
			}
		case "os":
			vn := "OS_TYPE_" + strings.ToUpper(v)
			type t = inventory.SchedulableLabels_OSType
			vals := inventory.SchedulableLabels_OSType_value
			*ls.OsType = t(vals[vn])
		case "phase":
			vn := "PHASE_" + strings.ToUpper(v)
			type t = inventory.SchedulableLabels_Phase
			vals := inventory.SchedulableLabels_Phase_value
			*ls.Phase = t(vals[vn])
		case "reference_design":
			*ls.ReferenceDesign = v
		case "variant":
			ls.Variant = append(ls.Variant, v)
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
