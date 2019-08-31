// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, arcConverter)
	reverters = append(reverters, arcReverter)
}

func arcConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	if ls.GetArc() {
		dims["label-arc"] = []string{"True"}
	}
}

func arcReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	d = assignLastBoolValueAndDropKey(d, ls.Arc, "label-arc")
	return d
}
