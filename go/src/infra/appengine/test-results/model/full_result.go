package model

import (
	"encoding/json"
	"errors"
	"math"
	"strings"
)

// FullResult represents "full_results.json".
type FullResult struct {
	Version        int            `json:"version"`
	Builder        string         `json:"builder_name"`
	BuildNumber    Number         `json:"build_number"`
	SecondsEpoch   int64          `json:"seconds_since_epoch"`
	Tests          FullTest       `json:"tests"`
	FailuresByType map[string]int `json:"num_failures_by_type"`

	// These fields are optional.

	ChromiumRev *string `json:"chromium_revision,omitempty"`
	PathDelim   *string `json:"path_delimiter,omitempty"`
	Interrupted *bool   `json:"interrupted,omitempty"`
	BlinkRev    *string `json:"blink_revision,omitempty"`

	// These fields are layout test specific.

	PrettyPatch       *bool   `json:"has_pretty_patch,omitempty"`
	Wdiff             *bool   `json:"has_wdiff"`
	LayoutTestsDir    *string `json:"layout_tests_dir,omitempty"`
	PixelTestsEnabled *bool   `json:"pixel_tests_enabled,omitempty"`

	// These fields are deprecated. However, uploaders still produce them:
	//   https://chromium.googlesource.com/chromium/src/+/530b8ac05b53ddc56a3787ad69bb1a843eee2f95/third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/models/test_run_results.py#172

	Fixable        *int `json:"fixable,omitempty"`
	NumFlaky       *int `json:"num_flaky,omitempty"`
	NumPasses      *int `json:"num_passes,omitempty"`
	NumRegressions *int `json:"num_regressions,omitempty"`
	Skips          *int `json:"skips,omitempty"`
}

// AggregateResult converts fr to an AggregateResult. The returned
// AggregateResult does not share references to objects referenced
// by fr.
func (fr *FullResult) AggregateResult() (AggregateResult, error) {
	cRev := []string{}
	if fr.ChromiumRev != nil {
		cRev = append(cRev, *fr.ChromiumRev)
	}

	failuresByType := make(map[string][]int)
	for k, v := range fr.FailuresByType {
		failuresByType[k] = []int{v}
	}

	tests, err := fr.Tests.AggregateTest()
	if err != nil {
		return AggregateResult{}, err
	}

	return AggregateResult{
		Version: ResultsVersion,
		Builder: fr.Builder,
		BuilderInfo: &BuilderInfo{
			SecondsEpoch:   []int64{fr.SecondsEpoch},
			BuildNumbers:   []Number{fr.BuildNumber},
			ChromeRevs:     cRev,
			Tests:          tests,
			FailureMap:     FailureLongNames,
			FailuresByType: failuresByType,
		},
	}, nil
}

// FullTest represents Tests in a FullResult.
type FullTest map[string]Node

var _ Node = (FullTest)(nil)

func (ft FullTest) node() {}

// FlatTest is a flattened representation of FullTest.
type FlatTest map[string]*FullTestLeaf

// FlatDelimiter is the separator for key names in FlatTest.
const FlatDelimiter = "/"

// Flatten flattens the test trie ft.
func (ft FullTest) Flatten() FlatTest {
	result := make(FlatTest)
	ft.flatten([]string(nil), result)
	return result
}

func (ft FullTest) flatten(prefixes []string, res FlatTest) {
	for key, node := range ft {
		switch t := node.(type) {
		case FullTest:
			t.flatten(append(prefixes, key), res)
		case *FullTestLeaf:
			res[strings.Join(append(prefixes, key), FlatDelimiter)] = t
		}
	}
}

// AggregateTest converts ft to an AggregateTest. The returned
// AggregateTest does not share references to objects referenced
// by ft.
func (ft FullTest) AggregateTest() (AggregateTest, error) {
	var aggr AggregateTest

	for k, v := range ft {
		if l, ok := v.(*FullTestLeaf); ok {
			aggrLeaf, err := l.AggregateTestLeaf()
			if err != nil {
				return nil, err
			}

			if aggr == nil {
				aggr = AggregateTest{}
			}
			aggr[k] = &aggrLeaf
			continue
		}

		child, ok := v.(FullTest)
		if !ok {
			return nil, errors.New("model: expected FullTest")
		}

		next, err := child.AggregateTest()
		if err != nil {
			return nil, err
		}

		if aggr == nil {
			aggr = AggregateTest{}
		}
		aggr[k] = next
	}

	return aggr, nil
}

// MarshalJSON marshals ft into JSON.
func (ft *FullTest) MarshalJSON() ([]byte, error) {
	if ft == nil {
		return json.Marshal(ft)
	}

	m := make(map[string]*json.RawMessage)

	for k, v := range *ft {
		b, err := json.Marshal(&v)
		if err != nil {
			return nil, err
		}
		raw := json.RawMessage(b)
		m[k] = &raw
	}

	return json.Marshal(m)
}

// UnmarshalJSON unmarshals the supplied data into ft.
func (ft *FullTest) UnmarshalJSON(data []byte) error {
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}
	if ft == nil {
		return errors.New("model: UnmarshalJSON: nil *FullTest")
	}
	if *ft == nil {
		*ft = FullTest{}
	}
	return ft.constructTree(m)
}

// constructTree constructs the tree of Nodes from the supplied map.
func (ft *FullTest) constructTree(m map[string]interface{}) error {
	for k, v := range m {
		mm, ok := v.(map[string]interface{})
		if !ok {
			continue
		}

		if isFullTestLeaf(mm) {
			l, err := makeFullTestLeaf(mm)
			if err != nil {
				return err
			}
			if *ft == nil {
				*ft = FullTest{}
			}
			(*ft)[k] = l
			continue
		}

		var child FullTest
		if err := child.constructTree(mm); err != nil {
			return err
		}
		if *ft == nil {
			*ft = FullTest{}
		}
		(*ft)[k] = child
	}

	return nil
}

// isFullTestLeaf returns true if the supplied map likely represents a
// FullTestLeaf.
func isFullTestLeaf(m map[string]interface{}) bool {
	for _, val := range m {
		if _, ok := val.(map[string]interface{}); ok {
			return false
		}
	}
	return true
}

// makeFullTestLeaf returns a FullTestLeaf from the supplied map.
func makeFullTestLeaf(m map[string]interface{}) (*FullTestLeaf, error) {
	l := &FullTestLeaf{}
	b, err := json.Marshal(m)
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(b, &l)
	return l, err
}

// FullTestLeaf represents the results for a particular test name.
type FullTestLeaf struct {
	Actual   []string `json:"-"`
	Expected []string `json:"-"`

	// These fields are optional.

	Runtime    *float64 `json:"time,omitempty"` // In seconds.
	Bugs       []string `json:"bugs"`
	Unexpected *bool    `json:"is_unexpected,omitempty"`

	// These fields are layout test specific.

	RepaintOverlay  *bool `json:"has_repaint_overlay,omitempty"`
	MissingAudio    *bool `json:"is_missing_audio,omitempty"`
	MissingText     *bool `json:"is_missing_text,omitempty"`
	MissingVideo    *bool `json:"is_missing_video,omitempty"`
	UsedTestHarness *bool `json:"is_testharness_test,omitempty"`
	// ReferenceTestType is documented at the JSON Test Results
	// Format (https://www.chromium.org/developers/the-json-test-results-format)
	// as string, but uploaders use []string.
	ReferenceTestType []string `json:"reftest_type,omitempty"`
}

var _ Node = (*FullTestLeaf)(nil)

func (l *FullTestLeaf) node() {}

// fullTestLeafAlias helps unmarshal and marshal FullTestLeaf.
type fullTestLeafAlias FullTestLeaf

// testResultAux helps unmarshal and marshal FullTestLeaf.
type testResultAux struct {
	Actual   string `json:"actual"`
	Expected string `json:"expected"`
	*fullTestLeafAlias
}

// AggregateTestLeaf converts l to AggregateTestLeaf. The returned
// AggregateTestLeaf does not share references to objects
// referenced by l.
//
// The returned error is always nil, but callers should check the
// error anyway because this behavior may change in the future.
func (l *FullTestLeaf) AggregateTestLeaf() (AggregateTestLeaf, error) {
	var ret AggregateTestLeaf

	expected := strings.Join(l.Expected, " ")
	actual := strings.Join(l.Actual, " ")

	if expected != "PASS" && expected != "NOTRUN" {
		ret.Expected = make([]string, len(l.Expected))
		copy(ret.Expected, l.Expected)
	}

	var shortFailures string
	if (expected != "SKIP" && actual == "SKIP") || expected == "NOTRUN" {
		shortFailures = "Y"
	} else {
		for _, f := range l.Actual {
			val, ok := FailureShortNames[f]
			if ok {
				shortFailures += val
			} else {
				shortFailures += "U"
			}
		}
	}
	ret.Results = []ResultSummary{{1, shortFailures}}

	if len(l.Bugs) > 0 {
		ret.Bugs = make([]string, len(l.Bugs))
		copy(ret.Bugs, l.Bugs)
	}

	var time float64
	if l.Runtime != nil {
		time = float64(round(*l.Runtime))
	}
	ret.Runtimes = []RuntimeSummary{{1, time}}

	return ret, nil
}

func round(f float64) int {
	if math.Abs(f) < 0.5 {
		return 0
	}
	return int(f + math.Copysign(0.5, f))
}

// MarshalJSON marshals l into JSON.
func (l *FullTestLeaf) MarshalJSON() ([]byte, error) {
	aux := testResultAux{fullTestLeafAlias: (*fullTestLeafAlias)(l)}
	aux.Actual = strings.Join(l.Actual, " ")
	aux.Expected = strings.Join(l.Expected, " ")
	return json.Marshal(&aux)
}

// UnmarshalJSON unmarshals the supplied data into l.
func (l *FullTestLeaf) UnmarshalJSON(data []byte) error {
	aux := testResultAux{fullTestLeafAlias: (*fullTestLeafAlias)(l)}
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}
	l.Actual = strings.Split(aux.Actual, " ")
	l.Expected = strings.Split(aux.Expected, " ")
	return nil
}

// Times represents "times_ms.json".
type Times map[string]float64
