// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, poolsConverter)
	converters = append(converters, selfServePoolsConverter)
}

func poolsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	vs := ls.GetCriticalPools()
	for _, v := range vs {
		const plen = 9 // len("DUT_POOL_")
		lv := "pool:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	return labels
}

func selfServePoolsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	vs := ls.GetSelfServePools()
	for _, v := range vs {
		lv := "pool:" + v
		labels = append(labels, lv)
	}
	return labels
}
