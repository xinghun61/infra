// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, ctsConverter)
	reverters = append(reverters, ctsReverter)
}

func ctsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	for _, v := range ls.GetCtsAbi() {
		const plen = 8 // len("CTS_ABI_")
		lv := "cts_abi_" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	for _, v := range ls.GetCtsCpu() {
		const plen = 8 // len("CTS_CPU_")
		lv := "cts_cpu_" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	return labels
}

func ctsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	for i := 0; i < len(labels); i++ {
		v := labels[i]
		switch {
		case strings.HasPrefix(v, "cts_abi_"):
			const plen = 8 // len("cts_abi_")
			vn := "CTS_ABI_" + strings.ToUpper(v[plen:])
			type t = inventory.SchedulableLabels_CTSABI
			vals := inventory.SchedulableLabels_CTSABI_value
			ls.CtsAbi = append(ls.CtsAbi, t(vals[vn]))
		case strings.HasPrefix(v, "cts_cpu_"):
			const plen = 8 // len("cts_cpu_")
			vn := "CTS_CPU_" + strings.ToUpper(v[plen:])
			type t = inventory.SchedulableLabels_CTSCPU
			vals := inventory.SchedulableLabels_CTSCPU_value
			ls.CtsCpu = append(ls.CtsCpu, t(vals[vn]))
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
