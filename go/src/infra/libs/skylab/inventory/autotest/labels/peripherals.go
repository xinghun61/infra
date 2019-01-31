// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"strings"

	"infra/libs/skylab/inventory"
)

func init() {
	converters = append(converters, boolPeripheralsConverter)
	converters = append(converters, otherPeripheralsConverter)

	reverters = append(reverters, boolPeripheralsReverter)
	reverters = append(reverters, otherPeripheralsReverter)
}

func boolPeripheralsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	p := ls.GetPeripherals()
	if p.GetAudioBoard() {
		labels = append(labels, "audio_board")
	}
	if p.GetAudioBox() {
		labels = append(labels, "audio_box")
	}
	if p.GetAudioLoopbackDongle() {
		labels = append(labels, "audio_loopback_dongle")
	}
	if p.GetChameleon() {
		labels = append(labels, "chameleon")
	}
	if p.GetConductive() {
		// Special case
		labels = append(labels, "conductive:True")
	}
	if p.GetHuddly() {
		labels = append(labels, "huddly")
	}
	if p.GetMimo() {
		labels = append(labels, "mimo")
	}
	if p.GetServo() {
		labels = append(labels, "servo")
	}
	if p.GetStylus() {
		labels = append(labels, "stylus")
	}
	if p.GetWificell() {
		labels = append(labels, "wificell")
	}
	return labels
}

func otherPeripheralsConverter(ls *inventory.SchedulableLabels) []string {
	var labels []string
	p := ls.GetPeripherals()
	if v := p.GetChameleonType(); v != inventory.Peripherals_CHAMELEON_TYPE_INVALID {
		const plen = 15 // len("CHAMELEON_TYPE_")
		lv := "chameleon:" + strings.ToLower(v.String()[plen:])
		labels = append(labels, lv)
	}
	return labels
}

func boolPeripheralsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	p := ls.GetPeripherals()
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "audio_board":
			*p.AudioBoard = true
		case "audio_box":
			*p.AudioBox = true
		case "audio_loopback_dongle":
			*p.AudioLoopbackDongle = true
		case "chameleon":
			if v != "" {
				continue
			}
			*p.Chameleon = true
		case "conductive":
			// Special case
			if v == "True" {
				*p.Conductive = true
			}
		case "huddly":
			*p.Huddly = true
		case "mimo":
			*p.Mimo = true
		case "servo":
			*p.Servo = true
		case "stylus":
			*p.Stylus = true
		case "wificell":
			*p.Wificell = true
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}

func otherPeripheralsReverter(ls *inventory.SchedulableLabels, labels []string) []string {
	p := ls.GetPeripherals()
	for i := 0; i < len(labels); i++ {
		k, v := splitLabel(labels[i])
		switch k {
		case "chameleon":
			if v == "" {
				continue
			}
			vn := "CHAMELEON_TYPE_" + strings.ToUpper(v)
			type t = inventory.Peripherals_ChameleonType
			vals := inventory.Peripherals_ChameleonType_value
			*p.ChameleonType = t(vals[vn])
		default:
			continue
		}
		labels = removeLabel(labels, i)
		i--
	}
	return labels
}
