// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolCapabilitiesConverter)
	reverters = append(reverters, boolCapabilitiesReverter)
	converters = append(converters, stringCapabilitiesConverter)
	reverters = append(reverters, stringCapabilitiesReverter)
	converters = append(converters, otherCapabilitiesConverter)
	reverters = append(reverters, otherCapabilitiesReverter)

}

func boolCapabilitiesConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
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

func boolCapabilitiesReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	c := ls.Capabilities
	d = assignLastBoolValueAndDropKey(d, c.Atrus, "label-atrus")
	d = assignLastBoolValueAndDropKey(d, c.Bluetooth, "label-bluetooth")
	d = assignLastBoolValueAndDropKey(d, c.Detachablebase, "label-detachablebase")
	d = assignLastBoolValueAndDropKey(d, c.Flashrom, "label-flashrom")
	d = assignLastBoolValueAndDropKey(d, c.Hotwording, "label-hotwording")
	d = assignLastBoolValueAndDropKey(d, c.InternalDisplay, "label-internal_display")
	d = assignLastBoolValueAndDropKey(d, c.Lucidsleep, "label-lucidsleep")
	d = assignLastBoolValueAndDropKey(d, c.Touchpad, "label-touchpad")
	d = assignLastBoolValueAndDropKey(d, c.Webcam, "label-webcam")
	return d
}

func stringCapabilitiesConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
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

func stringCapabilitiesReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	c := ls.Capabilities
	d = assignLastStringValueAndDropKey(d, c.GpuFamily, "label-gpu_family")
	d = assignLastStringValueAndDropKey(d, c.Graphics, "label-graphics")
	d = assignLastStringValueAndDropKey(d, c.Modem, "label-modem")
	d = assignLastStringValueAndDropKey(d, c.Power, "label-power")
	d = assignLastStringValueAndDropKey(d, c.Storage, "label-storage")
	d = assignLastStringValueAndDropKey(d, c.Telephony, "label-telephony")
	return d
}

func otherCapabilitiesConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	c := ls.GetCapabilities()
	if v := c.GetCarrier(); v != inventory.HardwareCapabilities_CARRIER_INVALID {
		dims["label-carrier"] = []string{v.String()}
	}
	for _, v := range c.GetVideoAcceleration() {
		appendDim(dims, "label-video_acceleration", v.String())
	}
}

func otherCapabilitiesReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	c := ls.Capabilities
	if v, ok := getLastStringValue(d, "label-carrier"); ok {
		if p, ok := inventory.HardwareCapabilities_Carrier_value[v]; ok {
			*c.Carrier = inventory.HardwareCapabilities_Carrier(p)
		}
		delete(d, "label-carrier")
	}
	c.VideoAcceleration = make([]inventory.HardwareCapabilities_VideoAcceleration, len(d["label-video_acceleration"]))
	for i, v := range d["label-video_acceleration"] {
		if p, ok := inventory.HardwareCapabilities_VideoAcceleration_value[v]; ok {
			c.VideoAcceleration[i] = inventory.HardwareCapabilities_VideoAcceleration(p)
		}
	}
	delete(d, "label-video_acceleration")
	return d
}
