// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolPeripheralsConverter)
	converters = append(converters, otherPeripheralsConverter)
}

func boolPeripheralsConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
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

func otherPeripheralsConverter(dims map[string][]string, ls *inventory.SchedulableLabels) {
	p := ls.GetPeripherals()
	if v := p.GetChameleonType(); v != inventory.Peripherals_CHAMELEON_TYPE_INVALID {
		dims["label-chameleon_type"] = []string{v.String()}
	}
}
