// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolCapabilitiesConverter)
	converters = append(converters, stringCapabilitiesConverter)
	converters = append(converters, otherCapabilitiesConverter)
}

func boolCapabilitiesConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	c := ls.GetCapabilities()
	if c.GetAtrus() {
		dims["label-atrus"] = []string{"True"}
	}
	if c.GetBluetooth() {
		dims["label-bluetooth"] = []string{"True"}
	}
	if c.GetDetachablebase() {
		dims["label-detachablebase"] = []string{"True"}
	}
	if c.GetFlashrom() {
		dims["label-flashrom"] = []string{"True"}
	}
	if c.GetHotwording() {
		dims["label-hotwording"] = []string{"True"}
	}
	if c.GetInternalDisplay() {
		dims["label-internal_display"] = []string{"True"}
	}
	if c.GetLucidsleep() {
		dims["label-lucidsleep"] = []string{"True"}
	}
	if c.GetTouchpad() {
		dims["label-touchpad"] = []string{"True"}
	}
	if c.GetWebcam() {
		dims["label-webcam"] = []string{"True"}
	}
}

func stringCapabilitiesConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	c := ls.GetCapabilities()
	if v := c.GetGpuFamily(); v != "" {
		dims["label-gpu_family"] = []string{v}
	}
	if v := c.GetGraphics(); v != "" {
		dims["label-graphics"] = []string{v}
	}
	if v := c.GetModem(); v != "" {
		dims["label-modem"] = []string{v}
	}
	if v := c.GetPower(); v != "" {
		dims["label-power"] = []string{v}
	}
	if v := c.GetStorage(); v != "" {
		dims["label-storage"] = []string{v}
	}
	if v := c.GetTelephony(); v != "" {
		dims["label-telephony"] = []string{v}
	}
}

func otherCapabilitiesConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	c := ls.GetCapabilities()
	if v := c.GetCarrier(); v != inventory.HardwareCapabilities_CARRIER_INVALID {
		dims["label-carrier"] = []string{v.String()}
	}
	for _, v := range c.GetVideoAcceleration() {
		appendDim(dims, "label-video_acceleration", v.String())
	}
}
