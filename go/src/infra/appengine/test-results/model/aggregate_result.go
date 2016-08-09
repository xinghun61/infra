package model

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"strconv"
	"strings"
)

// ResultsVersion is the latest version of the JSON format that "results.json"
// and "results-small.json" files are using.
const ResultsVersion = 4

var _ TestNode = (AggregateTest)(nil)
var _ TestNode = (*AggregateTestLeaf)(nil)

// CleanTestResultsJSON returns the result of removing a known prefix
// and suffix from the contents in r. If the prefix or suffix do not exist,
// the returned io.Reader has the same contents as r.
func CleanTestResultsJSON(r io.Reader) (io.Reader, error) {
	pre := []byte("ADD_RESULTS(")
	suf := []byte(");")

	b, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, err
	}

	if bytes.HasPrefix(b, pre) && bytes.HasSuffix(b, suf) {
		result := bytes.TrimPrefix(b, pre)
		result = bytes.TrimSuffix(result, suf)
		return bytes.NewReader(result), nil
	}

	return bytes.NewReader(b), nil
}

// AggregateResult represents "results.json" and "results-small.json" files.
// The Builder field must be set to the expected builder name before unmarshaling.
type AggregateResult struct {
	Version int
	Builder string
	*BuilderInfo
}

// BuilderInfo represents aggregate information about a builder.
type BuilderInfo struct {
	// SecondsEpoch is the start time of tests expressed in seconds from
	// the Unix epoch.
	SecondsEpoch []int64 `json:"secondsSinceEpoch"`

	BlinkRevs    []number `json:"blinkRevision"`
	BuildNumbers []number `json:"buildNumbers"`

	// ChromeRevs is a list of Chrome/Chromium revisions.
	// The elements are strings because they can either be revision
	// numbers or commit hashes.
	ChromeRevs []string `json:"chromeRevision"`

	// Tests is the test trie. The leaf nodes will be of type
	// AggregateTestLeaf.
	Tests AggregateTest `json:"tests"`

	// FailureMap is a map from long failure types to short failure
	// types. Usually, it resembles LongFailureTypes.
	FailureMap map[string]string `json:"failure_map"`

	// FailuresByType is a map from long failure type to
	// number of failures.
	FailuresByType map[string][]int `json:"num_failures_by_type,omitempty"`

	// FixableCounts represents test failures in a legacy format,
	// and is usually nil.
	//
	// It is included here because it may be needed to compute
	// FailuresByType when unmarshaling JSON.
	FixableCounts []map[string]int `json:"fixableCounts,omitempty"`
}

func (ag *AggregateResult) MarshalJSON() ([]byte, error) {
	v, err := json.Marshal(ag.Version)
	if err != nil {
		return nil, err
	}
	vRaw := json.RawMessage(v)

	info := *ag.BuilderInfo

	// If FailuresByType exists, do not include FixableCounts
	// because it is deprecated.
	if ag.FailuresByType != nil {
		info.FixableCounts = nil
	}

	b, err := json.Marshal(&info)
	if err != nil {
		return nil, err
	}
	infoRaw := json.RawMessage(b)

	return json.Marshal(map[string]*json.RawMessage{
		"version":  &vRaw,
		ag.Builder: &infoRaw,
	})
}

// UnmarshalJSON decodes JSON data into t.
//
// The expected format is a modified version of the format described in the URL
// below. The modifications account for the structure of results.json and
// results_small.json files in the wild.
//
//   https://chromium.googlesource.com/chromium/src/+/c7dd0560d9544a15908239bebc177410899851ca/third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/layout_package/bot_test_expectations.py#45
func (ag *AggregateResult) UnmarshalJSON(data []byte) error {
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}

	// Version.

	n, err := parseVersion(m)
	if err != nil {
		return err
	}
	ag.Version = n

	// BuilderInfo.

	raw, ok := m[ag.Builder]
	if !ok {
		return fmt.Errorf("model: missing builder: %s", ag.Builder)
	}

	var info *BuilderInfo
	if err := json.Unmarshal(raw, &info); err != nil {
		return err
	}
	ag.BuilderInfo = info

	if err := ag.checkFields(); err != nil {
		return err
	}
	if err := info.computeFailuresByType(); err != nil {
		return err
	}
	return info.checkFields()
}

func parseVersion(m map[string]json.RawMessage) (int, error) {
	vBytes, ok := m["version"]
	if !ok {
		return 0, errors.New("model: missing key version")
	}
	vStr := string(vBytes)

	n, err := strconv.Atoi(vStr)
	if err != nil {
		return 0, fmt.Errorf("model: version %q must be int: %v", vStr, err)
	}
	return n, nil
}

type fieldError struct {
	Name  string      // Name of field.
	Value interface{} // Invalid value in the field that caused error.
}

func (f fieldError) Error() string {
	return fmt.Sprintf("model: field %s has invalid value: %v", f.Name, f.Value)
}

func (ag *AggregateResult) checkFields() error {
	if ag.Version > ResultsVersion {
		return fieldError{"Version", ag.Version}
	}
	if ag.BuilderInfo == nil {
		return fieldError{"BuilderInfo", ag.BuilderInfo}
	}
	return nil
}

func (info *BuilderInfo) checkFields() error {
	if info.SecondsEpoch == nil {
		return fieldError{"SecondsEpoch", info.SecondsEpoch}
	}
	if info.BlinkRevs == nil {
		return fieldError{"BlinkRevs", info.BlinkRevs}
	}
	if info.BuildNumbers == nil {
		return fieldError{"BuildNumbers", info.BuildNumbers}
	}
	if info.ChromeRevs == nil {
		return fieldError{"ChromeRevs", info.ChromeRevs}
	}
	if info.Tests == nil {
		return fieldError{"Tests", info.Tests}
	}
	if info.FailureMap == nil {
		return fieldError{"FailureMap", info.FailureMap}
	}
	if info.FailuresByType == nil && info.FixableCounts == nil {
		return fieldError{"FailuresByType", info.FailuresByType}
	}
	return nil
}

// computeFailuresByType computes info.FailuresByType from info.FixableCounts.
// The function has no effect if info.FailuresByType is already non-nil.
func (info *BuilderInfo) computeFailuresByType() error {
	if info.FailuresByType != nil {
		// Already present.
		return nil
	}

	if info.FixableCounts == nil {
		return errors.New("model: nil FixableCounts")
	}

	res := make(map[string][]int)
	for _, fc := range info.FixableCounts {
		for short, count := range fc {
			long, ok := FailureLongNames[short]
			if !ok {
				return fmt.Errorf("model: unknown key: %s", short)
			}
			res[long] = append(res[long], count)
		}
	}

	info.FailuresByType = res
	return nil
}

// AggregateTest represents Tests in a AggregateResult.
type AggregateTest map[string]TestNode

func (at AggregateTest) Walk(fn func(key string, node TestNode) error) {
	for k, v := range at {
		if leaf, ok := v.(*AggregateTestLeaf); ok {
			if err := fn(k, leaf); err != nil {
				return
			}
			continue
		}

		if child, ok := v.(AggregateTest); ok {
			if err := fn(k, child); err != nil {
				return
			}
			child.Walk(fn)
		}
	}
}

func (at AggregateTest) WalkLeaves(fn func(key string, leaf *AggregateTestLeaf)) {
	at.Walk(func(k string, node TestNode) error {
		if leaf, ok := node.(*AggregateTestLeaf); ok {
			fn(k, leaf)
		}
		return nil
	})
}

func (at AggregateTest) Children() map[string]TestNode { return at }
func (at AggregateTest) testnode()                     {}

func (at AggregateTest) ToTestList() {
	at.WalkLeaves(func(_ string, leaf *AggregateTestLeaf) {
		leaf.Results = nil
		leaf.Runtimes = nil
	})
}

func (at *AggregateTest) MarshalJSON() ([]byte, error) {
	if at == nil {
		return json.Marshal(nil)
	}

	m := make(map[string]*json.RawMessage)

	for k, v := range *at {
		b, err := json.Marshal(&v)
		if err != nil {
			return nil, err
		}
		raw := json.RawMessage(b)
		m[k] = &raw
	}

	return json.Marshal(m)
}

func (at *AggregateTest) UnmarshalJSON(data []byte) error {
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}
	if at == nil {
		return errors.New("model: UnmarshalJSON on nil *AggregateTest")
	}
	if *at == nil {
		*at = AggregateTest{}
	}
	return at.constructTree(m)
}

// constructTree constructs the tree of test nodes from the supplied map.
func (at *AggregateTest) constructTree(m map[string]interface{}) error {
	for k, v := range m {
		mm, ok := v.(map[string]interface{})
		if !ok {
			continue
		}

		if isAggregateTestLeaf(mm) {
			l, err := makeAggregateTestLeaf(mm)
			if err != nil {
				return err
			}
			if *at == nil {
				*at = AggregateTest{}
			}
			(*at)[k] = l
			continue
		}

		var child AggregateTest
		if err := child.constructTree(mm); err != nil {
			return err
		}
		if *at == nil {
			*at = AggregateTest{}
		}
		(*at)[k] = child
	}

	return nil
}

// isAggregateTestLeaf returns true if the supplied map is likely represents a
// AggregateTestLeaf.
func isAggregateTestLeaf(m map[string]interface{}) bool {
	for key, val := range m {
		if key == "results" {
			if _, ok := val.([]interface{}); ok {
				return true
			}
		}
	}
	return false
}

// makeAggregateTestLeaf returns a AggregateTestLeaf from the supplied map.
func makeAggregateTestLeaf(m map[string]interface{}) (*AggregateTestLeaf, error) {
	l := &AggregateTestLeaf{}
	b, err := json.Marshal(m)
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(b, l)
	return l, err
}

// AggregateTestLeaf is the summary of test results at the l of a tests trie.
type AggregateTestLeaf struct {
	Results  []ResultSummary
	Runtimes []RuntimeSummary
	Expected []string
	Bugs     []string
}

// aggregateTestLeafAux is used to marshal and unmarshal AggregateTestLeaf.
type aggregateTestLeafAux struct {
	Results  []ResultSummary  `json:"results,omitempty"`
	Runtimes []RuntimeSummary `json:"times,omitempty"`
	Expected *string          `json:"expected,omitempty"`
	Bugs     []string         `json:"bugs,omitempty"`
}

func (l *AggregateTestLeaf) Children() map[string]TestNode { return nil }
func (l *AggregateTestLeaf) testnode()                     {}

func (l *AggregateTestLeaf) MarshalJSON() ([]byte, error) {
	aux := aggregateTestLeafAux{
		Results:  l.Results,
		Runtimes: l.Runtimes,
		Bugs:     l.Bugs,
	}
	if s := strings.Join(l.Expected, " "); len(s) > 0 {
		aux.Expected = &s
	}
	return json.Marshal(&aux)
}

func (l *AggregateTestLeaf) UnmarshalJSON(data []byte) error {
	var aux aggregateTestLeafAux
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	l.Results = aux.Results
	l.Runtimes = aux.Runtimes
	if aux.Expected != nil {
		l.Expected = strings.Split(*aux.Expected, " ")
	}
	l.Bugs = aux.Bugs

	return nil
}

// defaultFields sets default values for missing/invalid fields.
func (l *AggregateTestLeaf) defaultFields() {
	if len(l.Results) == 0 {
		l.Results = []ResultSummary{{1, "N"}}
	}
	if len(l.Runtimes) == 0 {
		l.Runtimes = []RuntimeSummary{{1, 0}}
	}
}

type ResultSummary struct {
	Count int
	Type  string
}

func (rs *ResultSummary) MarshalJSON() ([]byte, error) {
	return json.Marshal([]interface{}{
		rs.Count,
		rs.Type,
	})
}

func (rs *ResultSummary) UnmarshalJSON(data []byte) error {
	var tmp []interface{}
	if err := json.Unmarshal(data, &tmp); err != nil {
		return err
	}
	if len(tmp) != 2 {
		return fmt.Errorf("ResultSummary: wrong length: %d, expect: %d", len(tmp), 2)
	}

	count, ok := tmp[0].(float64)
	if !ok {
		return fmt.Errorf("ResultSummary: wrong format: %v", tmp)
	}
	rs.Count = int(count)

	rs.Type, ok = tmp[1].(string)
	if !ok {
		return fmt.Errorf("ResultSummary: wrong format: %v", tmp)
	}

	return nil
}

type RuntimeSummary struct {
	Count   int
	Runtime float64
}

func (rs *RuntimeSummary) MarshalJSON() ([]byte, error) {
	return json.Marshal([]float64{
		float64(rs.Count),
		rs.Runtime,
	})
}

func (rs *RuntimeSummary) UnmarshalJSON(data []byte) error {
	var tmp []float64
	if err := json.Unmarshal(data, &tmp); err != nil {
		return err
	}
	if len(tmp) != 2 {
		return fmt.Errorf("RuntimeSummary: wrong length: %d, expect: %d", len(tmp), 2)
	}

	rs.Count = int(tmp[0])
	rs.Runtime = tmp[1]
	return nil
}
