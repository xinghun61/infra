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

const fullTextProto = `
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
  chromesign: true
  chaos_dut: true
}
self_serve_pools: "poolval"
reference_design: "reef"
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
sku: "skuval"
hwid_sku: "eve_IntelR_CoreTM_i7_7Y75_CPU_1_30GHz_16GB"
brand: "HOMH"
ec_type: 1
cts_cpu: 1
cts_cpu: 2
cts_abi: 1
cts_abi: 2
critical_pools: 2
critical_pools: 1
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

var fullLabels = []string{
	"arc",
	"atrus",
	"audio_board",
	"audio_box",
	"audio_loopback_dongle",
	"bluetooth",
	"board:boardval",
	"brand-code:HOMH",
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
	"device-sku:skuval",
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
	"reference_design:reef",
	"servo",
	"sku:eve_IntelR_CoreTM_i7_7Y75_CPU_1_30GHz_16GB",
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
	if err := proto.UnmarshalText(fullTextProto, &ls); err != nil {
		t.Fatalf("Error unmarshalling example text: %s", err)
	}
	got := Convert(&ls)
	sort.Sort(sort.StringSlice(got))
	want := make([]string, len(fullLabels))
	copy(want, fullLabels)
	if diff := pretty.Compare(want, got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}

func TestRevertEmpty(t *testing.T) {
	t.Parallel()
	want := inventory.NewSchedulableLabels()
	got := Revert(nil)
	if diff := pretty.Compare(want, *got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}

func TestRevertFull(t *testing.T) {
	t.Parallel()
	var want inventory.SchedulableLabels
	if err := proto.UnmarshalText(fullTextProto, &want); err != nil {
		t.Fatalf("Error unmarshalling example text: %s", err)
	}
	labels := make([]string, len(fullLabels))
	copy(labels, fullLabels)
	got := Revert(labels)
	if diff := pretty.Compare(want, *got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}
