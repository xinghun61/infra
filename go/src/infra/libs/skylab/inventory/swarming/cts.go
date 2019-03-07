// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, ctsConverter)
}

func ctsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	for _, v := range ls.GetCtsAbi() {
		appendDim(dims, "label-cts_abi", v.String())
	}
	for _, v := range ls.GetCtsCpu() {
		appendDim(dims, "label-cts_cpu", v.String())
	}
}
