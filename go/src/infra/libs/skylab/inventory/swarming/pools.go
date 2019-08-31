// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, poolsConverter)
	converters = append(converters, selfServePoolsConverter)
	reverters = append(reverters, poolsReverter)
}

func poolsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	vs := ls.GetCriticalPools()
	for _, v := range vs {
		appendDim(dims, "label-pool", v.String())
	}
}

func selfServePoolsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	vs := ls.GetSelfServePools()
	for _, v := range vs {
		appendDim(dims, "label-pool", v)
	}
}

func poolsReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	for _, v := range d["label-pool"] {
		if p, ok := inventory.SchedulableLabels_DUTPool_value[v]; ok {
			ls.CriticalPools = append(ls.CriticalPools, inventory.SchedulableLabels_DUTPool(p))
		} else {
			ls.SelfServePools = append(ls.SelfServePools, v)
		}
	}
	delete(d, "label-pool")
	return d
}
