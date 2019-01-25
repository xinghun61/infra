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
