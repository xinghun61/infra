// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package userinput

import (
	"encoding/csv"
	"fmt"
	"infra/libs/skylab/inventory"
	"io"
	"io/ioutil"
	"regexp"
	"strings"

	"github.com/golang/protobuf/jsonpb"
	"go.chromium.org/luci/common/errors"
)

// GetDeviceSpecs interactively obtains inventory.DeviceUnderTest from the
// user.
//
// This function provides the user with initial specs, some help text and an
// example of a complete device spec.  User's updated specs are parsed and any
// errors are reported back to the user, allowing the user to fix the errors.
// promptFunc is used to prompt the user on parsing errors, to give them a
// choice to continue or abort the input session.
//
// Callers may pass a non-nil validateFunc to validate the user's updated
// specs. validateFunc is called within the userinput iteration loop described
// above, and errors are reported back to error in the same way as parsing
// errors.
//
// This function returns upon successful parsing of the user input, or upon
// user initiated abort.
func GetDeviceSpecs(initial *inventory.DeviceUnderTest, helpText string, promptFunc PromptFunc, validateFunc SpecsValidationFunc) (*inventory.DeviceUnderTest, error) {
	s := deviceSpecsGetter{
		inputFunc: func(initial []byte) ([]byte, error) {
			return textEditorInput(initial, "dutspecs.*.js")
		},
		promptFunc:   promptFunc,
		validateFunc: validateFunc,
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

// SpecsValidationFunc checks provided device specs for error.
//
// This function returns nil if provided specs are valid.
type SpecsValidationFunc func(*inventory.DeviceUnderTest) error

// deviceSpecsGetter provides methods to obtain user input via an interactive
// user session.
type deviceSpecsGetter struct {
	inputFunc    inputFunc
	promptFunc   PromptFunc
	validateFunc SpecsValidationFunc
}

func (s *deviceSpecsGetter) Get(initial *inventory.DeviceUnderTest, helpText string) (*inventory.DeviceUnderTest, error) {
	ui, err := serialize(initial)
	if err != nil {
		return nil, errors.Annotate(err, "get device specs").Err()
	}
	t, err := fullText(ui, helpText)
	if err != nil {
		return nil, errors.Annotate(err, "get device specs").Err()
	}
	for {
		i, err := s.inputFunc([]byte(t))
		if err != nil {
			return nil, errors.Annotate(err, "get device specs").Err()
		}
		t = string(i)
		d, err := s.parseAndValidate(t)
		if err != nil {
			if !s.promptFunc(err.Error()) {
				return nil, err
			}
			continue
		}
		return d, nil
	}
}

func (s *deviceSpecsGetter) parseAndValidate(t string) (*inventory.DeviceUnderTest, error) {
	d, err := parseUserInput(t)
	if err != nil {
		return nil, err
	}
	if s.validateFunc != nil {
		err = s.validateFunc(d)
	}
	return d, err
}

// fullText returns the text to provide for user input.
func fullText(userText string, helptext string) (string, error) {
	e, err := getExample()
	if err != nil {
		return "", errors.Annotate(err, "initial text").Err()
	}

	parts := []string{commentLines(header)}
	if helptext != "" {
		parts = append(parts, commentLines(helptext))
	}
	parts = append(parts, userText)
	parts = append(parts, commentLines(e))
	return strings.Join(parts, "\n\n"), nil
}

// parseUserInput parses the text obtained from the user.
func parseUserInput(text string) (*inventory.DeviceUnderTest, error) {
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

// GetMCSVText accepts a prompt and possibly a path and returns the text of the
// provided CSV file
func getMCSVText(specsFile string, mcsvFieldsPrompt string) (string, error) {
	var text string
	if specsFile == "" {
		rawText, err := textEditorInput([]byte(mcsvFieldsPrompt), `minimal-dutspecs.*.csv`)
		if err != nil {
			return "", err
		}
		text = string(rawText)
	} else {
		rawText, err := ioutil.ReadFile(specsFile)
		if err != nil {
			return "", err
		}
		text = string(rawText)
	}
	if text == "" {
		return "", errors.New(`mcsv file cannot be empty`)
	}
	return text, nil
}

// GetMCSVSpecs get a sequence of DeviceUnderTests in the MCSV format from the specified file.
func GetMCSVSpecs(specsFile string) ([]*inventory.DeviceUnderTest, error) {
	text, err := getMCSVText(specsFile, mcsvFieldsPrompt)
	if err != nil {
		return nil, err
	}
	return parseMCSV(text)
}

// parseMCSV takes a file in MCSV format and converts it into a list of inventory.DeviceUnderTest's
func parseMCSV(text string) ([]*inventory.DeviceUnderTest, error) {
	var out []*inventory.DeviceUnderTest

	reader := strings.NewReader(text)
	csvReader := csv.NewReader(reader)

	for linum := 1; ; linum++ {
		rec, err := csvReader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			e := errors.Annotate(err, fmt.Sprintf("malformed csv line %d", linum)).Err()
			return nil, e
		}
		// if linum is 1, determine whether this is a header
		if linum == 1 && looksLikeHeader(rec) {
			if err := validateSameStringArray(mcsvFields, rec); err != nil {
				return nil, err
			}
			continue
		}
		mcsvRecord, err := parseMcsvRecord(mcsvFields, rec)
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf(`malformed entry for csv file on line %d`, linum)).Err()
		}
		err = validateMcsvRecord(mcsvRecord)
		if err != nil {
			return nil, errors.Annotate(err, fmt.Sprintf(`nonconforming entry for csv file on line %d`, linum)).Err()
		}
		out = append(out, deviceUnderTestOfMcsvRecord(mcsvRecord))
	}

	return out, nil
}

func looksLikeHeader(rec []string) bool {
	if len(rec) == 0 {
		return false
	}
	return rec[0] == "host"
}

func parseMcsvRecord(header []string, rec []string) (*mcsvRecord, error) {
	out := &mcsvRecord{}
	if len(header) != len(rec) {
		return nil, errors.New(fmt.Sprintf("length mismatch: expected (%d) actual (%d)", len(header), len(rec)))
	}
	for i := range header {
		name := header[i]
		value := rec[i]
		switch name {
		case "host":
			out.host = value
		case "model":
			out.model = value
		case "board":
			out.board = value
		case "servo_host", "servoHost":
			out.servoHost = value
		case "servo_port", "servoPort":
			out.servoPort = value
		case "servo_serial", "servoSerial":
			out.servoSerial = value
		case "powerunit_hostname", "powerunitHostname":
			out.powerunitHostname = value
		case "powerunit_outlet", "powerunitOutlet":
			out.powerunitOutlet = value
		default:
			return nil, errors.New(fmt.Sprintf(`unknown field: %s`, name))
		}
	}
	return out, nil
}

func dutAddAttribute(dut *inventory.DeviceUnderTest, key string, value string) {
	kv := &inventory.KeyValue{
		Key:   &key,
		Value: &value,
	}
	dut.Common.Attributes = append(dut.Common.Attributes, kv)
}

func deviceUnderTestOfMcsvRecord(rec *mcsvRecord) *inventory.DeviceUnderTest {
	out := &inventory.DeviceUnderTest{
		Common: &inventory.CommonDeviceSpecs{
			Labels: &inventory.SchedulableLabels{},
		},
	}
	out.Common.Hostname = &rec.host
	out.Common.Labels.Board = &rec.board
	out.Common.Labels.Model = &rec.model
	dutAddAttribute(out, `servo_host`, rec.servoHost)
	dutAddAttribute(out, `servo_port`, rec.servoPort)
	dutAddAttribute(out, `servo_serial`, rec.servoSerial)
	dutAddAttribute(out, `powerunit_hostname`, rec.powerunitHostname)
	dutAddAttribute(out, `powerunit_outlet`, rec.powerunitOutlet)
	return out
}

func validateSameStringArray(expected []string, actual []string) error {
	if len(expected) != len(actual) {
		return errors.New("length mismatch")
	}
	for i, e := range expected {
		a := actual[i]
		if e != a {
			return fmt.Errorf("item mismatch at position (%d) expected (%s) got (%s)", i, e, a)
		}
	}
	return nil
}

func serialize(dut *inventory.DeviceUnderTest) (string, error) {
	m := jsonpb.Marshaler{
		EnumsAsInts: false,
		Indent:      "  ",
	}
	var w strings.Builder
	err := m.Marshal(&w, dut)
	return w.String(), err
}

func deserialize(text string) (*inventory.DeviceUnderTest, error) {
	var dut inventory.DeviceUnderTest
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

var mcsvFields = []string{
	"host",
	"board",
	"model",
	"servo_host",
	"servo_port",
	"servo_serial",
	"powerunit_hostname",
	"powerunit_outlet",
}

const mcsvFieldsPrompt = `host,board,model,servo_host,servo_port,servo_serial,powerunit_hostname,powerunit_outlet`

type mcsvRecord struct {
	host              string
	board             string
	model             string
	servoHost         string
	servoPort         string
	servoSerial       string
	powerunitHostname string
	powerunitOutlet   string
}

func validateMcsvRecord(rec *mcsvRecord) error {
	if rec.host == "" {
		return errors.New("host cannot be empty")
	}
	if rec.board == "" {
		return errors.New("board cannot be empty")
	}
	if rec.model == "" {
		return errors.New("model cannot be empty")
	}
	if rec.servoHost == "" {
		return errors.New("servo_host cannot be empty")
	}
	if rec.servoPort == "" {
		return errors.New("servo_port cannot be empty")
	}
	if rec.servoSerial == "" {
		return errors.New("servo_serial cannot be empty")
	}
	if rec.powerunitHostname == "" {
		return errors.New("powerunit_hostname cannot be empty")
	}
	if rec.powerunitOutlet == "" {
		return errors.New("powerunit_outlet cannot be empty")
	}
	return nil
}

const commentPrefix = "// "

var commentDetectionPattern = regexp.MustCompile(`^(\s)*//`)

const header = `
This is a template for adding / updating common device specs.

All lines starting with # will be ignored.

An example of fully populated specs is provided at the bottom as a reference.
The actual values included are examples only and may not be sensible defaults
for your device.`

const example = `{
	"common": {
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
	}
}`
