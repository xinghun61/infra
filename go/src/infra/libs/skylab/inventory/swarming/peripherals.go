// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolPeripheralsConverter)
	reverters = append(reverters, boolPeripheralsReverter)
	converters = append(converters, otherPeripheralsConverter)
	reverters = append(reverters, otherPeripheralsReverter)
}

func boolPeripheralsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	p := ls.GetPeripherals()
	if p.GetAudioBoard() {
		dims["label-audio_board"] = []string{"True"}
	}
	if p.GetAudioBox() {
		dims["label-audio_box"] = []string{"True"}
	}
	if p.GetAudioLoopbackDongle() {
		dims["label-audio_loopback_dongle"] = []string{"True"}
	}
	if p.GetChameleon() {
		dims["label-chameleon"] = []string{"True"}
	}
	if p.GetConductive() {
		dims["label-conductive"] = []string{"True"}
	}
	if p.GetHuddly() {
		dims["label-huddly"] = []string{"True"}
	}
	if p.GetMimo() {
		dims["label-mimo"] = []string{"True"}
	}
	if p.GetServo() {
		dims["label-servo"] = []string{"True"}
	}
	if p.GetStylus() {
		dims["label-stylus"] = []string{"True"}
	}
	if p.GetWificell() {
		dims["label-wificell"] = []string{"True"}
	}
}

func boolPeripheralsReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	p := ls.Peripherals
	d = assignLastBoolValueAndDropKey(d, p.AudioBoard, "label-audio_board")
	d = assignLastBoolValueAndDropKey(d, p.AudioBox, "label-audio_box")
	d = assignLastBoolValueAndDropKey(d, p.AudioLoopbackDongle, "label-audio_loopback_dongle")
	d = assignLastBoolValueAndDropKey(d, p.Chameleon, "label-chameleon")
	d = assignLastBoolValueAndDropKey(d, p.Conductive, "label-conductive")
	d = assignLastBoolValueAndDropKey(d, p.Huddly, "label-huddly")
	d = assignLastBoolValueAndDropKey(d, p.Mimo, "label-mimo")
	d = assignLastBoolValueAndDropKey(d, p.Servo, "label-servo")
	d = assignLastBoolValueAndDropKey(d, p.Stylus, "label-stylus")
	d = assignLastBoolValueAndDropKey(d, p.Wificell, "label-wificell")
	return d
}

func otherPeripheralsConverter(dims Dimensions, ls *inventory.SchedulableLabels) {
	p := ls.GetPeripherals()
	if v := p.GetChameleonType(); v != inventory.Peripherals_CHAMELEON_TYPE_INVALID {
		dims["label-chameleon_type"] = []string{v.String()}
	}
}

func otherPeripheralsReverter(ls *inventory.SchedulableLabels, d Dimensions) Dimensions {
	p := ls.Peripherals
	if v, ok := getLastStringValue(d, "label-chameleon_type"); ok {
		if ct, ok := inventory.Peripherals_ChameleonType_value[v]; ok {
			*p.ChameleonType = inventory.Peripherals_ChameleonType(ct)
		}
		delete(d, "label-chameleon_type")
	}
	return d
}
