// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, arcConverter)
}

func arcConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	if ls.GetArc() {
		dims["label-arc"] = []string{"True"}
	}
}
