// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

// NewSchedulableLabels returns a new zero value instance of SchedulableLabels.
func NewSchedulableLabels() *SchedulableLabels {
	return &SchedulableLabels{
		Arc:   new(bool),
		Board: new(string),
		Brand: new(string),
		Capabilities: &HardwareCapabilities{
			Atrus:           new(bool),
			Bluetooth:       new(bool),
			Detachablebase:  new(bool),
			Carrier:         new(HardwareCapabilities_Carrier),
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
		Cr50Phase: new(SchedulableLabels_CR50_Phase),
		EcType:    new(SchedulableLabels_ECType),
		Model:     new(string),
		Sku:       new(string),
		OsType:    new(SchedulableLabels_OSType),
		Peripherals: &Peripherals{
			AudioBoard:          new(bool),
			AudioBox:            new(bool),
			AudioLoopbackDongle: new(bool),
			Chameleon:           new(bool),
			ChameleonType:       new(Peripherals_ChameleonType),
			Conductive:          new(bool),
			Huddly:              new(bool),
			Mimo:                new(bool),
			Servo:               new(bool),
			Stylus:              new(bool),
			Wificell:            new(bool),
		},
		Platform:        new(string),
		Phase:           new(SchedulableLabels_Phase),
		ReferenceDesign: new(string),
		TestCoverageHints: &TestCoverageHints{
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
