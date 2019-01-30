// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package hostinfo

import (
	"infra/libs/skylab/inventory"
	"infra/libs/skylab/inventory/autotest/labels"
)

// ConvertDut converts the inventory DUT struct to Autotest hostinfo.
func ConvertDut(d *inventory.DeviceUnderTest) *HostInfo {
	var hi HostInfo
	convertDutAttributes(&hi, d)
	convertDutLabels(&hi, d)
	return &hi
}

func convertDutAttributes(hi *HostInfo, d *inventory.DeviceUnderTest) {
	if hi.Attributes == nil {
		hi.Attributes = make(map[string]string)
	}
	for _, a := range d.GetCommon().GetAttributes() {
		hi.Attributes[a.GetKey()] = a.GetValue()
	}
}

func convertDutLabels(hi *HostInfo, d *inventory.DeviceUnderTest) {
	sl := d.GetCommon().GetLabels()
	hi.Labels = labels.Convert(sl)
}
