// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"go.chromium.org/chromiumos/infra/proto/go/device"
)

// ConvertDeviceConfig converts device configs to the git-based skylab inventory.
func ConvertDeviceConfig(dc *device.Config, spec *CommonDeviceSpecs) {
	// In case spec labels don't contain capabilities or peripherals.
	c := spec.GetLabels().GetCapabilities()
	if c == nil {
		spec.GetLabels().Capabilities = &HardwareCapabilities{}
		c = spec.GetLabels().GetCapabilities()
	}
	p := spec.GetLabels().GetPeripherals()
	if p == nil {
		spec.GetLabels().Peripherals = &Peripherals{}
		p = spec.GetLabels().GetPeripherals()
	}
	c.Carrier = new(HardwareCapabilities_Carrier)
	switch dc.GetCarrier() {
	case "att":
		*c.Carrier = HardwareCapabilities_CARRIER_ATT
	case "tmobile":
		*c.Carrier = HardwareCapabilities_CARRIER_TMOBILE
	case "verizon":
		*c.Carrier = HardwareCapabilities_CARRIER_VERIZON
	case "sprint":
		*c.Carrier = HardwareCapabilities_CARRIER_SPRINT
	default:
		*c.Carrier = HardwareCapabilities_CARRIER_INVALID
	}

	c.GpuFamily = new(string)
	*c.GpuFamily = dc.GetGpuFamily()

	c.Graphics = new(string)
	switch dc.GetGraphics() {
	case device.Config_GRAPHICS_GL:
		*c.Graphics = "gl"
	case device.Config_GRAPHICS_GLE:
		*c.Graphics = "gles"
	default:
		*c.Graphics = ""
	}

	for _, hf := range dc.GetHardwareFeatures() {
		switch hf {
		case device.Config_HARDWARE_FEATURE_BLUETOOTH:
			c.Bluetooth = new(bool)
			*c.Bluetooth = true
		case device.Config_HARDWARE_FEATURE_FLASHROM:
			*c.Flashrom = true
		case device.Config_HARDWARE_FEATURE_HOTWORDING:
			c.Hotwording = new(bool)
			*c.Hotwording = true
		case device.Config_HARDWARE_FEATURE_INTERNAL_DISPLAY:
			c.InternalDisplay = new(bool)
			*c.InternalDisplay = true
		case device.Config_HARDWARE_FEATURE_LUCID_SLEEP:
			c.Lucidsleep = new(bool)
			*c.Lucidsleep = true
		case device.Config_HARDWARE_FEATURE_WEBCAM:
			c.Webcam = new(bool)
			*c.Webcam = true
		case device.Config_HARDWARE_FEATURE_STYLUS:
			p.Stylus = new(bool)
			*p.Stylus = true
		case device.Config_HARDWARE_FEATURE_TOUCHPAD:
			c.Touchpad = new(bool)
			*c.Touchpad = true
		case device.Config_HARDWARE_FEATURE_TOUCHSCREEN:
		default:
		}
	}

	c.Power = new(string)
	switch dc.GetPower() {
	case device.Config_POWER_SUPPLY_AC_ONLY:
		*c.Power = "AC_only"
	case device.Config_POWER_SUPPLY_BATTERY:
		*c.Power = "battery"
	case device.Config_POWER_SUPPLY_UNSPECIFIED:
		*c.Power = ""
	}

	c.Storage = new(string)
	switch dc.GetStorage() {
	case device.Config_STORAGE_HDD:
		*c.Storage = "hdd"
	case device.Config_STORAGE_MMC:
		*c.Storage = "mmc"
	case device.Config_STORAGE_NVME:
		*c.Storage = "nvme"
	case device.Config_STORAGE_SSD:
		*c.Storage = "ssd"
	case device.Config_STORAGE_UFS:
		*c.Storage = "ufs"
	case device.Config_STORAGE_UNSPECIFIED:
		*c.Storage = ""
	}

	c.VideoAcceleration = nil
	for _, hf := range dc.GetVideoAccelerationSupports() {
		switch hf {
		case device.Config_VIDEO_ACCELERATION_H264:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_H264)
		case device.Config_VIDEO_ACCELERATION_ENC_H264:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_ENC_H264)
		case device.Config_VIDEO_ACCELERATION_VP8:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_VP8)
		case device.Config_VIDEO_ACCELERATION_ENC_VP8:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_ENC_VP8)
		case device.Config_VIDEO_ACCELERATION_VP9:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_VP9)
		case device.Config_VIDEO_ACCELERATION_ENC_VP9:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_ENC_VP9)
		case device.Config_VIDEO_ACCELERATION_VP9_2:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_VP9_2)
		case device.Config_VIDEO_ACCELERATION_ENC_VP9_2:
			c.VideoAcceleration = append(c.VideoAcceleration, HardwareCapabilities_VIDEO_ACCELERATION_ENC_VP9_2)
		default:
		}
	}
}

// CopyDCAmongLabels copy device configs between two schedulable labels.
func CopyDCAmongLabels(to *SchedulableLabels, from *SchedulableLabels) {
	toC := to.GetCapabilities()
	fromC := from.GetCapabilities()
	toC.Carrier = fromC.Carrier
	toC.GpuFamily = fromC.GpuFamily
	toC.Graphics = fromC.Graphics
	toC.Power = fromC.Power
	toC.Storage = fromC.Storage
	toC.VideoAcceleration = fromC.VideoAcceleration
	toC.Bluetooth = fromC.Bluetooth
	toC.InternalDisplay = fromC.InternalDisplay
	toC.Webcam = fromC.Webcam
	toC.Flashrom = fromC.Flashrom
	toC.Hotwording = fromC.Hotwording
	toC.Lucidsleep = fromC.Lucidsleep
	toC.Touchpad = fromC.Touchpad
	to.GetPeripherals().Stylus = from.GetPeripherals().Stylus
}
