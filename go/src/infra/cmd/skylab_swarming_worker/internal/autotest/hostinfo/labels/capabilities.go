// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolCapabilitiesConverter)
	converters = append(converters, stringCapabilitiesConverter)
	converters = append(converters, otherCapabilitiesConverter)
}

func boolCapabilitiesConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	c := ls.GetCapabilities()
	if c.GetAtrus() {
		labels = append(labels, "atrus")
	}
	if c.GetBluetooth() {
		labels = append(labels, "bluetooth")
	}
	if c.GetDetachablebase() {
		labels = append(labels, "detachablebase")
	}
	if c.GetFlashrom() {
		labels = append(labels, "flashrom")
	}
	if c.GetHotwording() {
		labels = append(labels, "hotwording")
	}
	if c.GetInternalDisplay() {
		labels = append(labels, "internal_display")
	}
	if c.GetLucidsleep() {
		labels = append(labels, "lucidsleep")
	}
	if c.GetTouchpad() {
		labels = append(labels, "touchpad")
	}
	if c.GetWebcam() {
		labels = append(labels, "webcam")
	}
	return labels
}

func stringCapabilitiesConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	c := ls.GetCapabilities()
	if v := c.GetGpuFamily(); v != "" {
		lv := "gpu_family:" + v
		labels = append(labels, lv)
	}
	if v := c.GetGraphics(); v != "" {
		lv := "graphics:" + v
		labels = append(labels, lv)
	}
	if v := c.GetModem(); v != "" {
		lv := "modem:" + v
		labels = append(labels, lv)
	}
	if v := c.GetPower(); v != "" {
		lv := "power:" + v
		labels = append(labels, lv)
	}
	if v := c.GetTelephony(); v != "" {
		lv := "telephony:" + v
		labels = append(labels, lv)
	}
	if v := c.GetStorage(); v != "" {
		lv := "storage:" + v
		labels = append(labels, lv)
	}
	return labels
}

func otherCapabilitiesConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	c := ls.GetCapabilities()
	if v := c.GetCarrier(); v != inventory.HardwareCapabilities_CARRIER_INVALID {
		const plen = 8 // len("CARRIER_")
		lv := "carrier:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	for _, v := range c.GetVideoAcceleration() {
		const plen = 19 // len("VIDEO_ACCELERATION_")
		lv := "hw_video_acc_" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	return labels
}
