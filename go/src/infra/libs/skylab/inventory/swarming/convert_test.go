// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package swarming

import (
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
phase: 8
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
cr50_phase: 0
cts_cpu: 1
cts_cpu: 2
cts_abi: 1
cts_abi: 2
critical_pools: 1
critical_pools: 2
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
  internal_display: true
  graphics: "graphicsval"
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

var fullDimensions = Dimensions{
	"label-arc":                   {"True"},
	"label-atrus":                 {"True"},
	"label-audio_board":           {"True"},
	"label-audio_box":             {"True"},
	"label-audio_loopback_dongle": {"True"},
	"label-bluetooth":             {"True"},
	"label-board":                 {"boardval"},
	"label-carrier":               {"CARRIER_TMOBILE"},
	"label-chameleon":             {"True"},
	"label-chameleon_type":        {"CHAMELEON_TYPE_DP_HDMI"},
	"label-chaos_dut":             {"True"},
	"label-chromesign":            {"True"},
	"label-conductive":            {"True"},
	"label-cts_abi":               {"CTS_ABI_ARM", "CTS_ABI_X86"},
	"label-cts_cpu":               {"CTS_CPU_ARM", "CTS_CPU_X86"},
	"label-detachablebase":        {"True"},
	"label-ec_type":               {"EC_TYPE_CHROME_OS"},
	"label-flashrom":              {"True"},
	"label-gpu_family":            {"gpufamilyval"},
	"label-graphics":              {"graphicsval"},
	"label-hangout_app":           {"True"},
	"label-hwid_sku":              {"eve_IntelR_CoreTM_i7_7Y75_CPU_1_30GHz_16GB"},
	"label-hotwording":            {"True"},
	"label-huddly":                {"True"},
	"label-internal_display":      {"True"},
	"label-meet_app":              {"True"},
	"label-mimo":                  {"True"},
	"label-model":                 {"modelval"},
	"label-modem":                 {"modemval"},
	"label-lucidsleep":            {"True"},
	"label-os_type":               {"OS_TYPE_CROS"},
	"label-phase":                 {"PHASE_MP"},
	"label-platform":              {"platformval"},
	"label-pool":                  {"DUT_POOL_CQ", "DUT_POOL_BVT", "poolval"},
	"label-power":                 {"powerval"},
	"label-recovery_test":         {"True"},
	"label-reference_design":      {"reef"},
	"label-touchpad":              {"True"},
	"label-servo":                 {"True"},
	"label-sku":                   {"skuval"},
	"label-brand":                 {"HOMH"},
	"label-storage":               {"storageval"},
	"label-stylus":                {"True"},
	"label-telephony":             {"telephonyval"},
	"label-test_audiojack":        {"True"},
	"label-test_hdmiaudio":        {"True"},
	"label-test_usbaudio":         {"True"},
	"label-test_usbprinting":      {"True"},
	"label-usb_detect":            {"True"},
	"label-variant":               {"somevariant"},
	"label-video_acceleration": {
		"VIDEO_ACCELERATION_ENC_VP9",
		"VIDEO_ACCELERATION_ENC_VP9_2",
	},
	"label-webcam":   {"True"},
	"label-wificell": {"True"},
}

func TestConvertEmpty(t *testing.T) {
	t.Parallel()
	ls := inventory.SchedulableLabels{}
	got := Convert(&ls)
	if len(got) > 0 {
		t.Errorf("Got nonempty dimensions %#v", got)
	}
}

func TestConvertFull(t *testing.T) {
	t.Parallel()
	var ls inventory.SchedulableLabels
	if err := proto.UnmarshalText(fullTextProto, &ls); err != nil {
		t.Fatalf("Error unmarshalling example text: %s", err)
	}
	got := Convert(&ls)
	if diff := pretty.Compare(fullDimensions, got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}

func TestRevertEmpty(t *testing.T) {
	t.Parallel()
	want := inventory.NewSchedulableLabels()
	got := Revert(make(Dimensions))
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
	got := Revert(cloneDimensions(fullDimensions))
	if diff := pretty.Compare(want, *got); diff != "" {
		t.Errorf("labels differ -want +got, %s", diff)
	}
}

func cloneDimensions(d Dimensions) Dimensions {
	ret := make(Dimensions)
	for k, v := range d {
		ret[k] = make([]string, len(v))
		copy(ret[k], v)
	}
	return ret
}
