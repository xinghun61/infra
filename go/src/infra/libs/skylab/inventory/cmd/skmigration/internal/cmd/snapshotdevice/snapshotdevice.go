// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package snapshotdevice

// SnapshotDevice refers to the structure of autotest's lab device data.
// TODO(gregorynisbet): Use proto serialization rather than ad hoc data type.
type SnapshotDevice struct {
	AutotestLabels []string `json:"autotest-labels"`
	Common         struct {
		Attributes []struct {
			Key   string `json:"key"`
			Value string `json:"value"`
		} `json:"attributes"`
		Hostname string `json:"hostname"`
		ID       string `json:"id"`
		Labels   struct {
			Arc          bool   `json:"arc"`
			Board        string `json:"board"`
			Capabilities struct {
				Atrus             bool     `json:"atrus"`
				Bluetooth         bool     `json:"bluetooth"`
				Carrier           string   `json:"carrier"`
				Detachablebase    bool     `json:"detachablebase"`
				Flashrom          bool     `json:"flashrom"`
				GpuFamily         string   `json:"gpuFamily"`
				Graphics          string   `json:"graphics"`
				Hotwording        bool     `json:"hotwording"`
				InternalDisplay   bool     `json:"internalDisplay"`
				Lucidsleep        bool     `json:"lucidsleep"`
				Modem             string   `json:"modem"`
				Power             string   `json:"power"`
				Storage           string   `json:"storage"`
				Telephony         string   `json:"telephony"`
				Touchpad          bool     `json:"touchpad"`
				VideoAcceleration []string `json:"videoAcceleration"`
				Webcam            bool     `json:"webcam"`
			} `json:"capabilities"`
			Cr50Phase     string   `json:"cr50Phase"`
			CriticalPools []string `json:"criticalPools"`
			CtsAbi        []string `json:"ctsAbi"`
			CtsCPU        []string `json:"ctsCpu"`
			EcType        string   `json:"ecType"`
			Model         string   `json:"model"`
			OsType        string   `json:"osType"`
			Peripherals   struct {
				AudioBoard          bool   `json:"audioBoard"`
				AudioBox            bool   `json:"audioBox"`
				AudioLoopbackDongle bool   `json:"audioLoopbackDongle"`
				Chameleon           bool   `json:"chameleon"`
				ChameleonType       string `json:"chameleonType"`
				Conductive          bool   `json:"conductive"`
				Huddly              bool   `json:"huddly"`
				Mimo                bool   `json:"mimo"`
				Servo               bool   `json:"servo"`
				Stylus              bool   `json:"stylus"`
				Wificell            bool   `json:"wificell"`
			} `json:"peripherals"`
			Phase             string `json:"phase"`
			Platform          string `json:"platform"`
			ReferenceDesign   string `json:"referenceDesign"`
			Sku               string `json:"sku"`
			TestCoverageHints struct {
				ChaosDut        bool `json:"chaosDut"`
				Chromesign      bool `json:"chromesign"`
				HangoutApp      bool `json:"hangoutApp"`
				MeetApp         bool `json:"meetApp"`
				RecoveryTest    bool `json:"recoveryTest"`
				TestAudiojack   bool `json:"testAudiojack"`
				TestHdmiaudio   bool `json:"testHdmiaudio"`
				TestUsbaudio    bool `json:"testUsbaudio"`
				TestUsbprinting bool `json:"testUsbprinting"`
				UsbDetect       bool `json:"usbDetect"`
			} `json:"testCoverageHints"`
			Variant []string `json:"variant"`
		} `json:"labels"`
	} `json:"common"`
}
