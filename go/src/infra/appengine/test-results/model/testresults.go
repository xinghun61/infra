package model

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"

	commerr "github.com/luci/luci-go/common/errors"
)

// TODO(nishanths): Use better JSON structure and key names. Will need
// refactoring of other services that depend on this code.

// number is an integer that supports JSON unmarshaling from a string
// and marshaling back to a string. Unmarshal and Marshal on this
// type are not inverse operations if the original string was
// "-0" or that of a positive integer starting with "+".
type number int

func (n *number) UnmarshalJSON(data []byte) error {
	data = bytes.Trim(data, `"`)
	num, err := strconv.Atoi(string(data))
	if err != nil {
		return err
	}
	*n = number(num)
	return nil
}

func (n *number) MarshalJSON() ([]byte, error) {
	return []byte(strconv.Itoa(int(*n))), nil
}

// BuilderDetails represents information about tests for a builder.
type BuilderDetails struct {
	SecondsSinceEpoch []int                  `json:"secondsSinceEpoch"`
	BlinkRevision     []number               `json:"blinkRevision"`
	BuildNumbers      []number               `json:"buildNumbers"`
	ChromeRevision    []number               `json:"chromeRevision"`
	Tests             map[string]interface{} `json:"tests"`
	FailureMap        map[string]string      `json:"failure_map"`

	// FailuresByType is a map from long failure type name to number of failures.
	// This field is nil if the parsed JSON did not contain the
	// "num_failures_by_type" key, or the failures by type could not be computed
	// from FixableCounts.
	FailuresByType map[string][]int `json:"num_failures_by_type,omitempty"`

	// FixableCounts represents test failures in a legacy format. This field is
	// nil if the parsed JSON did not contain the "fixableCounts" key.
	FixableCounts []map[string]int `json:"fixableCounts,omitempty"`
}

// TestResults represents aggregate test results in results.json or
// results-small.json files. The Builder field must be set to the expected
// builder name before unmarshaling.
type TestResults struct {
	Version int
	Builder string
	BuilderDetails
}

// computeFailuresByType computes FailuresByType from FixableCounts.
//
// It has no effect if FailuresByType is already non-nil. The returned
// error is non-nil if both FailuresByType and FixableCounts
// are nil, or FixableCounts has an unexpected format.
func (bd *BuilderDetails) computeFailuresByType() error {
	if bd.FailuresByType != nil {
		// Already present.
		return nil
	}
	if bd.FixableCounts == nil {
		return errors.New("need FixableCounts to be non-nil to compute FailuresByType")
	}

	res := make(map[string][]int)
	for _, fc := range bd.FixableCounts {
		for shortType, count := range fc {
			longType, ok := failureTypes[shortType]
			if !ok {
				return fmt.Errorf("failed to convert FixableCounts to FailuresByType: unknown key: %s", shortType)
			}
			res[longType] = append(res[longType], count)
		}
	}

	bd.FailuresByType = res
	return nil
}

func (bd *BuilderDetails) checkFields() error {
	var errs commerr.MultiError

	if bd.SecondsSinceEpoch == nil {
		errs = append(errs, errors.New("expected <secondsSinceEpoch> to not be nil"))
	}
	if bd.BlinkRevision == nil {
		errs = append(errs, errors.New("expected <blinkRevision> to not be nil"))
	}
	if bd.BuildNumbers == nil {
		errs = append(errs, errors.New("expected <buildNumbers> to not be nil"))
	}
	if bd.ChromeRevision == nil {
		errs = append(errs, errors.New("expected <chromeRevision> to not be nil"))
	}
	if bd.Tests == nil {
		errs = append(errs, errors.New("expected <tests> to not be nil"))
	}
	if bd.FailureMap == nil {
		errs = append(errs, errors.New("expected <failure_map> to not be nil"))
	}
	if bd.FailuresByType == nil {
		errs = append(errs, errors.New("expected <num_failures_by_type> to not be nil"))
	}

	if len(errs) == 0 {
		return nil
	}
	return errs
}

// MarshalJSON encodes TestResults in the format expected by clients.
func (t *TestResults) MarshalJSON() ([]byte, error) {
	v, err := json.Marshal(t.Version)
	if err != nil {
		return nil, err
	}
	vRaw := json.RawMessage(v)

	// Do not include FixableCounts even if present because it is deprecated.
	builderDet := t.BuilderDetails
	builderDet.FixableCounts = nil

	bd, err := json.Marshal(builderDet)
	if err != nil {
		return nil, err
	}
	bdRaw := json.RawMessage(bd)

	return json.Marshal(map[string]*json.RawMessage{
		"version": &vRaw,
		t.Builder: &bdRaw,
	})
}

// UnmarshalJSON decodes JSON data into t.
//
// Expected format:
//
//    {
//      'version': 4,
//      'builder name' : {
//        'blinkRevision': [],
//        'tests': {
//          'directory' { # Each path component is a dictionary.
//            'testname.html': {
//              'expected' : 'FAIL', # Expectation name.
//              'results': [], # Run-length encoded result.
//              'times': [],
//              'bugs': [], # Bug URLs.
//            }
//          }
//        }
//        'buildNumbers': [],
//        'secondsSinceEpoch': [],
//        'chromeRevision': [],
//        'failure_map': {},  # Map from letter code to expectation name.
//        'num_failures_by_type': {}
//      }
//    }
//
// The expected format is a modified version of the format described in the URL
// below. The modifications accounts for the structure of results.json and results-small.json
// files in the wild.
//
//   https://cs.chromium.org/chromium/src/third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/layout_package/bot_test_expectations.py?type=cs&q=blinkRevision&sq=package:chromium&l=45
//
// TODO(nishanths): Describe expected format formally.
func (t *TestResults) UnmarshalJSON(data []byte) error {
	const maxVersion = 4

	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}

	// Version.
	versionRaw, ok := m["version"]
	if !ok {
		return errors.New("missing <version> key")
	}
	ver, err := strconv.Atoi(string(versionRaw))
	if err != nil {
		return fmt.Errorf("expected <version> to be int, got %q: %v", string(versionRaw), err)
	}
	if ver > maxVersion {
		return fmt.Errorf("expected <version> to not be greater than %d, got %d", maxVersion, ver)
	}
	t.Version = ver

	// BuilderDetails.
	builderRaw, ok := m[t.Builder]
	if !ok {
		return fmt.Errorf("missing builder <%s>", t.Builder)
	}
	if string(builderRaw) == "null" {
		return fmt.Errorf("builder <%s> has null value", t.Builder)
	}
	var bd BuilderDetails
	if err := json.Unmarshal(builderRaw, &bd); err != nil {
		return err
	}
	if err := bd.computeFailuresByType(); err != nil {
		return err
	}
	t.BuilderDetails = bd

	return bd.checkFields()
}
