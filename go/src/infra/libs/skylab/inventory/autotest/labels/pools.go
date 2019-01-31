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

	reverters = append(reverters, poolsReverter)
	reverters = append(reverters, selfServePoolsReverter)
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

func poolsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "pool":
			vn := "DUT_POOL_" + strings.ToUpper(v)
			type t = inventory.SchedulableLabels_DUTPool
			vals := inventory.SchedulableLabels_DUTPool_value
			if vals[vn] == 0 {
				continue
			}
			ls.CriticalPools = append(ls.CriticalPools, t(vals[vn]))
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}

func selfServePoolsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "pool":
			vn := "DUT_POOL_" + strings.ToUpper(v)
			type t = inventory.SchedulableLabels_DUTPool
			vals := inventory.SchedulableLabels_DUTPool_value
			if vals[vn] != 0 {
				continue
			}
			ls.SelfServePools = append(ls.SelfServePools, v)
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
