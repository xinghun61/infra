// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
	"strings"
)

func init() {
	converters = append(converters, basicConverter)
	reverters = append(reverters, basicReverter)
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
	if v := ls.GetBrand(); v != "" {
		dims["label-brand"] = []string{v}
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

func basicReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	d = assignLastStringValueAndDropKey(d, ls.Board, "label-board")
	d = assignLastStringValueAndDropKey(d, ls.Model, "label-model")
	d = assignLastStringValueAndDropKey(d, ls.Sku, "label-sku")
	d = assignLastStringValueAndDropKey(d, ls.Brand, "label-brand")
	d = assignLastStringValueAndDropKey(d, ls.Platform, "label-platform")
	d = assignLastStringValueAndDropKey(d, ls.ReferenceDesign, "label-reference_design")
	if v, ok := getLastStringValue(d, "label-ec_type"); ok {
		if ec, ok := inventory.SchedulableLabels_ECType_value[v]; ok {
			*ls.EcType = inventory.SchedulableLabels_ECType(ec)
		}
		delete(d, "label-ec_type")
	}
	if v, ok := getLastStringValue(d, "label-os_type"); ok {
		if ot, ok := inventory.SchedulableLabels_OSType_value[v]; ok {
			*ls.OsType = inventory.SchedulableLabels_OSType(ot)
		}
		delete(d, "label-os_type")
	}
	if v, ok := getLastStringValue(d, "label-phase"); ok {
		if p, ok := inventory.SchedulableLabels_Phase_value[v]; ok {
			*ls.Phase = inventory.SchedulableLabels_Phase(p)
		}
		delete(d, "label-phase")
	}
	ls.Variant = append(ls.Variant, d["label-variant"]...)
	delete(d, "label-variant")
	return d
}

func assignLastStringValueAndDropKey(d Dimensions, to *string, key string) Dimensions {
	if v, ok := getLastStringValue(d, key); ok {
		*to = v
	}
	delete(d, key)
	return d
}

func getLastStringValue(d Dimensions, key string) (string, bool) {
	if vs, ok := d[key]; ok {
		if len(vs) > 0 {
			return vs[len(vs)-1], true
		}
		return "", false
	}
	return "", false
}

func assignLastBoolValueAndDropKey(d Dimensions, to *bool, key string) Dimensions {
	if v, ok := getLastBoolValue(d, key); ok {
		*to = v
	}
	delete(d, key)
	return d
}

func getLastBoolValue(d Dimensions, key string) (bool, bool) {
	if s, ok := getLastStringValue(d, key); ok {
		return strings.ToLower(s) == "true", true
	}
	return false, false
}
