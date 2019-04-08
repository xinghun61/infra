// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package userinput

import (
	"infra/libs/skylab/inventory"
	"regexp"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/luci/common/errors"
)

// GetDeviceSpecs interactively obtains inventory.CommonDeviceSpecs from the
// user.
//
// This function provides the user with initial specs, some help text and an
// example of a complete device spec.  User's updated specs are parsed and any
// errors are reported back to the user, allowing the user to fix the errors.
// promptFunc is used to prompt the user on parsing errors, to give them a
// choice to continue or abort the input session.
//
// This function returns upon successful parsing of the user input, or upon
// user initiated abort.
func GetDeviceSpecs(initial *inventory.CommonDeviceSpecs, helpText string, promptFunc PromptFunc) (*inventory.CommonDeviceSpecs, error) {
	s := deviceSpecsGetter{
		inputFunc:  textEditorInput,
		promptFunc: promptFunc,
	}
	return s.Get(initial, helpText)
}

// inputFunc obtains text input from user.
//
// inputFunc takes an initial text to display to the user and returns the
// user-modified text.
type inputFunc func([]byte) ([]byte, error)

// PromptFunc obtains consent from the user for the given request string.
//
// This function is used to provide the user some context through the provided
// string and then obtain a yes/no answer from the user.
type PromptFunc func(string) bool

// deviceSpecsGetter provides methods to obtain user input via an interactive
// user session.
type deviceSpecsGetter struct {
	inputFunc  inputFunc
	promptFunc PromptFunc
}

func (s *deviceSpecsGetter) Get(initial *inventory.CommonDeviceSpecs, helpText string) (*inventory.CommonDeviceSpecs, error) {
	t, err := initialText(initial, helpText)
	if err != nil {
		return nil, errors.Annotate(err, "get device specs").Err()
	}

	for {
		i, err := s.inputFunc([]byte(t))
		if err != nil {
			return nil, errors.Annotate(err, "get device specs").Err()
		}
		d, err := parseUserInput(string(i))
		if err != nil {
			if !s.promptFunc(err.Error()) {
				return nil, err
			}
			continue
		}
		return d, nil
	}
}

// initialText returns the text to provide for user input.
func initialText(dut *inventory.CommonDeviceSpecs, helptext string) (string, error) {
	t, err := serialize(dut)
	if err != nil {
		return "", errors.Annotate(err, "intitial text").Err()
	}
	e, err := getExample()
	if err != nil {
		return "", errors.Annotate(err, "initial text").Err()
	}

	parts := []string{commentLines(header)}
	if helptext != "" {
		parts = append(parts, commentLines(helptext))
	}
	parts = append(parts, t)
	parts = append(parts, commentLines(e))
	return strings.Join(parts, "\n\n"), nil
}

// parseUserInput parses the text obtained from the user.
func parseUserInput(text string) (*inventory.CommonDeviceSpecs, error) {
	text = dropCommentLines(text)
	dut, err := deserialize(text)
	if err != nil {
		return nil, errors.Annotate(err, "parse user input").Err()
	}
	return dut, nil
}

func getExample() (string, error) {
	e, err := deserialize(example)
	if err != nil {
		return "", errors.Annotate(err, "get example").Err()
	}
	t, err := serialize(e)
	if err != nil {
		return "", errors.Annotate(err, "get example").Err()
	}
	return t, nil
}

func serialize(dut *inventory.CommonDeviceSpecs) (string, error) {
	m := jsonpb.Marshaler{
		EnumsAsInts: false,
		Indent:      "  ",
	}
	var w strings.Builder
	err := m.Marshal(&w, dut)
	return w.String(), err
}

func deserialize(text string) (*inventory.CommonDeviceSpecs, error) {
	var dut inventory.CommonDeviceSpecs
	err := jsonpb.Unmarshal(strings.NewReader(text), &dut)
	return &dut, err
}

// commentLines converts each line in text to comment lines.
func commentLines(text string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if !isCommented(line) {
			lines[i] = commentPrefix + line
		}
	}
	return strings.Join(lines, "\n")
}

// dropCommentLines drops lines from text that are comment lines, commented
// using commentLines().
func dropCommentLines(text string) string {
	lines := strings.Split(text, "\n")
	filtered := make([]string, 0, len(lines))
	for _, line := range lines {
		if !isCommented(line) {
			filtered = append(filtered, line)
		}
	}
	return strings.Join(filtered, "\n")
}

func isCommented(line string) bool {
	// Valid match cannot be empty because it at least contains commentPrefix.
	return commentDetectionPattern.FindString(line) != ""
}

const commentPrefix = "# "

var commentDetectionPattern = regexp.MustCompile(`^(\s)*#`)

const header = `
This is a template for adding / updating common device specs.

All lines starting with # will be ignored.

An example of fully populated specs is provided at the bottom as a reference.
The actual values included are examples only and may not be sensible defaults
for your device.`

const example = `{
	"attributes": [
		{
			"key": "HWID",
			"value": "BLAZE E2A-E3G-B5D-A37"
		},
		{
			"key": "powerunit_hostname",
			"value": "chromeos4-row7_8-rack7-rpm2"
		},
		{
			"key": "powerunit_outlet",
			"value": ".A11"
		},
		{
			"key": "serial_number",
			"value": "5CD45009QJ"
		},
		{
			"key": "stashed_labels",
			"value": "board_freq_mem:nyan_blaze_2.1GHz_4GB,sku:blaze_cpu_nyan_4Gb"
		}
	],
	"environment": "ENVIRONMENT_STAGING",
	"hostname": "chromeos4-row7-rack7-host11",
	"id": "140e9f86-ffef-49ea-bb07-40494e0b0481",
	"labels": {
		"arc": false,
		"board": "nyan_blaze",
		"capabilities": {
			"atrus": false,
			"bluetooth": true,
			"carrier": "CARRIER_INVALID",
			"detachablebase": false,
			"flashrom": false,
			"gpuFamily": "tegra",
			"graphics": "gles",
			"hotwording": false,
			"internalDisplay": true,
			"lucidsleep": false,
			"modem": "",
			"power": "battery",
			"storage": "mmc",
			"telephony": "",
			"webcam": true,
			"touchpad": true,
			"videoAcceleration": [
				"VIDEO_ACCELERATION_H264",
				"VIDEO_ACCELERATION_ENC_H264",
				"VIDEO_ACCELERATION_VP8",
				"VIDEO_ACCELERATION_ENC_VP8"
			]
		},
		"cr50Phase": "CR50_PHASE_INVALID",
		"criticalPools": [
			"DUT_POOL_SUITES",
			"DUT_POOL_SUITES"
		],
		"ctsAbi": [
			"CTS_ABI_ARM"
		],
		"ecType": "EC_TYPE_CHROME_OS",
		"model": "nyan_blaze",
		"osType": "OS_TYPE_CROS",
		"peripherals": {
			"audioBoard": false,
			"audioBox": false,
			"audioLoopbackDongle": true,
			"chameleon": false,
			"chameleonType": "CHAMELEON_TYPE_INVALID",
			"conductive": false,
			"huddly": false,
			"mimo": false,
			"servo": true,
			"stylus": false,
			"wificell": false
		},
		"phase": "PHASE_MP",
		"platform": "nyan_blaze",
		"referenceDesign": "",
		"testCoverageHints": {
			"chaosDut": false,
			"chromesign": false,
			"hangoutApp": false,
			"meetApp": false,
			"recoveryTest": false,
			"testAudiojack": false,
			"testHdmiaudio": false,
			"testUsbaudio": false,
			"testUsbprinting": false,
			"usbDetect": false
		}
	},
	"serialNumber": "5CD45009QJ"
}`
