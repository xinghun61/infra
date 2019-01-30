// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package labels

import (
	"sort"
	"testing"

	"github.com/golang/protobuf/proto"
	"github.com/kylelemons/godebug/pretty"

	"infra/libs/skylab/inventory"
)

func TestConvertEmpty(t *testing.T) {
	t.Parallel()
	ls := inventory.SchedulableLabels{}
	got := Convert(&ls)
	if len(got) > 0 {
		t.Errorf("Got nonempty labels %#v", got)
	}
}

func TestConvertFull(t *testing.T) {
	t.Parallel()
	var ls inventory.SchedulableLabels
	text := `
variant: "somevariant"
test_coverage_hints {
  usb_detect: true
  test_usbprinting: true
  test_usbaudio: true
  test_hdmiaudio: true
  test_audiojack: true
  recovery_test: true
  meet_app: true
  hangout_app: true
  cts_sparse: 2
  chromesign: true
  chaos_dut: true
}
self_serve_pools: "poolval"
platform: "platformval"
phase: 4
peripherals: {
  wificell: true
  stylus: true
  servo: true
  mimo: true
  huddly: true
  conductive: true
  chameleon_type: 3
  chameleon: true
  audio_loopback_dongle: true
  audio_box: true
  audio_board: true
}
os_type: 2
model: "modelval"
ec_type: 1
cts_cpu: 1
cts_cpu: 2
cts_abi: 1
cts_abi: 2
critical_pools: 1
critical_pools: 2
cr50_phase: 2
capabilities {
  webcam: true
  video_acceleration: 6
  video_acceleration: 8
  touchpad: true
  telephony: "telephonyval"
  storage: "storageval"
  power: "powerval"
  modem: "modemval"
  lucidsleep: true
  hotwording: true
  graphics: "graphicsval"
  internal_display: true
  gpu_family: "gpufamilyval"
  flashrom: true
  detachablebase: true
  carrier: 2
  bluetooth: true
  atrus: true
}
board: "boardval"
arc: true
`
	if err := proto.UnmarshalText(text, &ls); err != nil {
		t.Fatalf("Error unmarshalling example text: %s", err)
	}
	got := Convert(&ls)
	sort.Sort(sort.StringSlice(got))
	want := []string{
		"arc",
		"atrus",
		"audio_board",
		"audio_box",
		"audio_loopback_dongle",
		"bluetooth",
		"board:boardval",
		"carrier:tmobile",
		"chameleon",
		"chameleon:dp_hdmi",
		"chaos_dut",
		"chromesign",
		"conductive:True",
		"cr50:pvt",
		"cts_abi_arm",
		"cts_abi_x86",
		"cts_cpu_arm",
		"cts_cpu_x86",
		"detachablebase",
		"ec:cros",
		"flashrom",
		"gpu_family:gpufamilyval",
		"graphics:graphicsval",
		"hangout_app",
		"hotwording",
		"huddly",
		"hw_video_acc_enc_vp9",
		"hw_video_acc_enc_vp9_2",
		"internal_display",
		"lucidsleep",
		"meet_app",
		"mimo",
		"model:modelval",
		"modem:modemval",
		"os:cros",
		"phase:DVT2",
		"platform:platformval",
		"pool:bvt",
		"pool:cq",
		"pool:poolval",
		"power:powerval",
		"recovery_test",
		"servo",
		"sparse_coverage_3",
		"storage:storageval",
		"stylus",
		"telephony:telephonyval",
		"test_audiojack",
		"test_hdmiaudio",
		"test_usbaudio",
		"test_usbprinting",
		"touchpad",
		"usb_detect",
		"variant:somevariant",
		"webcam",
		"wificell",
	}
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}
