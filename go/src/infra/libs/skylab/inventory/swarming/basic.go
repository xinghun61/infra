// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, basicConverter)
}

func basicConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	if v := ls.GetBoard(); v != "" {
		dims["label-board"] = []string{v}
	}
	if v := ls.GetModel(); v != "" {
		dims["label-model"] = []string{v}
	}
	if v := ls.GetSku(); v != "" {
		dims["label-sku"] = []string{v}
	}
	if v := ls.GetPlatform(); v != "" {
		dims["label-platform"] = []string{v}
	}
	if v := ls.GetReferenceDesign(); v != "" {
		dims["label-reference_design"] = []string{v}
	}
	if v := ls.GetEcType(); v != inventory.SchedulableLabels_EC_TYPE_INVALID {
		dims["label-ec_type"] = []string{v.String()}
	}
	if v := ls.GetOsType(); v != inventory.SchedulableLabels_OS_TYPE_INVALID {
		dims["label-os_type"] = []string{v.String()}
	}
	if v := ls.GetPhase(); v != inventory.SchedulableLabels_PHASE_INVALID {
		dims["label-phase"] = []string{v.String()}
	}
	for _, v := range ls.GetVariant() {
		appendDim(dims, "label-variant", v)
	}
}
