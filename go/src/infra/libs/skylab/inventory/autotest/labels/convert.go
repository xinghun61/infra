// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package labels implements conversion of Skylab inventory schema to
// Autotest labels.
package labels

import "infra/libs/skylab/inventory"

// Convert converts DUT inventory labels to Autotest labels.
func Convert(ls *inventory.SchedulableLabels) []string {
	var labels []string
	for _, c := range converters {
		labels = append(labels, c(ls)...)
	}
	return labels
}

var converters []converter

// converter is the type of functions used for converting Skylab
// inventory labels to Autotest labels.  Each converter should return
// the Autotest labels it is responsible for.
type converter func(*inventory.SchedulableLabels) []string

// Revert converts DUT inventory labels to Autotest labels.
func Revert(labels []string) *inventory.SchedulableLabels {
	ls := newScheduableLabels()
	for _, r := range reverters {
		labels = r(ls, labels)
	}
	return ls
}

var reverters []reverter

// reverter is the type of functions used for reverting Autotest
// labels back to Skylab inventory labels.  Each reverter should
// modify the SchedulableLabels for the Autotest labels it is
// responsible for, and return a slice of Autotest labels that it does
// not handle.
type reverter func(*inventory.SchedulableLabels, []string) []string

func newScheduableLabels() *inventory.SchedulableLabels {
	return &inventory.SchedulableLabels{
		Arc:   new(bool),
		Board: new(string),
		Capabilities: &inventory.HardwareCapabilities{
			Atrus:           new(bool),
			Bluetooth:       new(bool),
			Detachablebase:  new(bool),
			Carrier:         new(inventory.HardwareCapabilities_Carrier),
			Flashrom:        new(bool),
			GpuFamily:       new(string),
			Graphics:        new(string),
			Hotwording:      new(bool),
			InternalDisplay: new(bool),
			Lucidsleep:      new(bool),
			Modem:           new(string),
			Power:           new(string),
			Storage:         new(string),
			Telephony:       new(string),
			Touchpad:        new(bool),
			Webcam:          new(bool),
		},
		Cr50Phase: new(inventory.SchedulableLabels_CR50_Phase),
		EcType:    new(inventory.SchedulableLabels_ECType),
		Model:     new(string),
		OsType:    new(inventory.SchedulableLabels_OSType),
		Peripherals: &inventory.Peripherals{
			AudioBoard:          new(bool),
			AudioBox:            new(bool),
			AudioLoopbackDongle: new(bool),
			Chameleon:           new(bool),
			ChameleonType:       new(inventory.Peripherals_ChameleonType),
			Conductive:          new(bool),
			Huddly:              new(bool),
			Mimo:                new(bool),
			Servo:               new(bool),
			Stylus:              new(bool),
			Wificell:            new(bool),
		},
		Platform: new(string),
		Phase:    new(inventory.SchedulableLabels_Phase),
		TestCoverageHints: &inventory.TestCoverageHints{
			ChaosDut:        new(bool),
			Chromesign:      new(bool),
			HangoutApp:      new(bool),
			MeetApp:         new(bool),
			RecoveryTest:    new(bool),
			TestAudiojack:   new(bool),
			TestHdmiaudio:   new(bool),
			TestUsbaudio:    new(bool),
			TestUsbprinting: new(bool),
			UsbDetect:       new(bool),
		},
	}
}
