// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolTestCoverageHintsConverter)
	reverters = append(reverters, boolTestCoverageHintsReverter)
}

func boolTestCoverageHintsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	h := ls.GetTestCoverageHints()
	if h.GetChaosDut() {
		dims["label-chaos_dut"] = []string{"True"}
	}
	if h.GetChromesign() {
		dims["label-chromesign"] = []string{"True"}
	}
	if h.GetHangoutApp() {
		dims["label-hangout_app"] = []string{"True"}
	}
	if h.GetMeetApp() {
		dims["label-meet_app"] = []string{"True"}
	}
	if h.GetRecoveryTest() {
		dims["label-recovery_test"] = []string{"True"}
	}
	if h.GetTestAudiojack() {
		dims["label-test_audiojack"] = []string{"True"}
	}
	if h.GetTestHdmiaudio() {
		dims["label-test_hdmiaudio"] = []string{"True"}
	}
	if h.GetTestUsbaudio() {
		dims["label-test_usbaudio"] = []string{"True"}
	}
	if h.GetTestUsbprinting() {
		dims["label-test_usbprinting"] = []string{"True"}
	}
	if h.GetUsbDetect() {
		dims["label-usb_detect"] = []string{"True"}
	}
}

func boolTestCoverageHintsReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	h := ls.TestCoverageHints
	d = assignLastBoolValueAndDropKey(d, h.ChaosDut, "label-chaos_dut")
	d = assignLastBoolValueAndDropKey(d, h.Chromesign, "label-chromesign")
	d = assignLastBoolValueAndDropKey(d, h.HangoutApp, "label-hangout_app")
	d = assignLastBoolValueAndDropKey(d, h.MeetApp, "label-meet_app")
	d = assignLastBoolValueAndDropKey(d, h.RecoveryTest, "label-recovery_test")
	d = assignLastBoolValueAndDropKey(d, h.TestAudiojack, "label-test_audiojack")
	d = assignLastBoolValueAndDropKey(d, h.TestHdmiaudio, "label-test_hdmiaudio")
	d = assignLastBoolValueAndDropKey(d, h.TestUsbaudio, "label-test_usbaudio")
	d = assignLastBoolValueAndDropKey(d, h.TestUsbprinting, "label-test_usbprinting")
	d = assignLastBoolValueAndDropKey(d, h.UsbDetect, "label-usb_detect")

	return d
}
