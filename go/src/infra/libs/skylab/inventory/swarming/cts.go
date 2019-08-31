// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, ctsConverter)
	reverters = append(reverters, ctsReverter)
}

func ctsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	for _, v := range ls.GetCtsAbi() {
		appendDim(dims, "label-cts_abi", v.String())
	}
	for _, v := range ls.GetCtsCpu() {
		appendDim(dims, "label-cts_cpu", v.String())
	}
}

func ctsReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	ls.CtsAbi = make([]inventory.SchedulableLabels_CTSABI, len(d["label-cts_abi"]))
	for i, v := range d["label-cts_abi"] {
		if p, ok := inventory.SchedulableLabels_CTSABI_value[v]; ok {
			ls.CtsAbi[i] = inventory.SchedulableLabels_CTSABI(p)
		}
	}
	delete(d, "label-cts_abi")
	ls.CtsCpu = make([]inventory.SchedulableLabels_CTSCPU, len(d["label-cts_cpu"]))
	for i, v := range d["label-cts_cpu"] {
		if p, ok := inventory.SchedulableLabels_CTSCPU_value[v]; ok {
			ls.CtsCpu[i] = inventory.SchedulableLabels_CTSCPU(p)
		}
	}
	delete(d, "label-cts_cpu")
	return d
}
