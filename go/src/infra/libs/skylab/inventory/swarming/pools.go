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
