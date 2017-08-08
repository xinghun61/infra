// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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

var (
	// CleanPrefix is the prefix that CleanJSON removes.
	CleanPrefix = []byte("ADD_RESULTS(")
	// CleanSuffix is the suffix that CleanJSON removes.
	CleanSuffix = []byte(");")
)

// CleanJSON returns the result of removing CleanPrefix
// and CleanSuffix from the contents in r. If either
// CleanPrefix or CleanSuffix does not exist, the returned
// io.Reader has the same contents as r.
func CleanJSON(r io.Reader) (io.Reader, error) {
	b, err := ioutil.ReadAll(r)
	if err != nil {
		return nil, err
	}

	if bytes.HasPrefix(b, CleanPrefix) && bytes.HasSuffix(b, CleanSuffix) {
		result := bytes.TrimPrefix(b, CleanPrefix)
		result = bytes.TrimSuffix(result, CleanSuffix)
		return bytes.NewReader(result), nil
	}

	return bytes.NewReader(b), nil
}

// AggregateResult represents "results.json" and "results-small.json" files.
type AggregateResult struct {
	Version int
	Builder string
	*BuilderInfo
}

// BuilderInfo represents aggregate information for a builder.
type BuilderInfo struct {
	// SecondsEpoch is the start time of tests expressed in seconds from
	// the Unix epoch.
	SecondsEpoch []float64 `json:"secondsSinceEpoch"`

	// BlinkRevs is list of Blink revisions.
	BlinkRevs []Number `json:"blinkRevision"`

	// BuildNumbers is list of build numbers.
	BuildNumbers []Number `json:"buildNumbers"`

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

// TestList is a representation an AggregateResult in which
// the Results and Runtimes fields of all the AggregateTestLeafs
// are set to nil.
type TestList struct {
	Builder string
	Tests   AggregateTest
}

// MarshalJSON marshals tl into JSON.
func (tl *TestList) MarshalJSON() ([]byte, error) {
	return json.Marshal(map[string]map[string]AggregateTest{
		tl.Builder: {
			"tests": tl.Tests,
		},
	})
}

// ToTestList returns a TestList representation of ag.
// The receiver's Tests field will be modified in the process.
func (ag *AggregateResult) ToTestList() TestList {
	tl := TestList{
		Builder: ag.Builder,
		Tests:   ag.Tests,
	}
	tl.Tests.WalkLeaves(func(_ string, leaf *AggregateTestLeaf) {
		leaf.Results = nil
		leaf.Runtimes = nil
	})
	return tl
}

// MarshalJSON marshal ag into JSON.
func (ag *AggregateResult) MarshalJSON() ([]byte, error) {
	v, err := json.Marshal(ag.Version)
	if err != nil {
		return nil, err
	}
	vRaw := json.RawMessage(v)

	info := *ag.BuilderInfo

	// If FailuresByType exists, do not include FixableCounts
	// because it is deprecated.
	if info.FailuresByType != nil {
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

// extractBuilderName gets the builder name from the supplied map.
// This depends on the fact that AggregateResults are expected to
// only have two top-level keys: (1) "version" (2) the builder name.
func extractBuilderName(m map[string]json.RawMessage) (string, error) {
	for k := range m {
		if k != "version" {
			return k, nil
		}
	}
	return "", errors.New("builder name not found")
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

	// Builder name.

	builder, err := extractBuilderName(m)
	if err != nil {
		return err
	}
	ag.Builder = builder

	// BuilderInfo.

	var info *BuilderInfo
	if err := json.Unmarshal(m[builder], &info); err != nil {
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

func (f *fieldError) Error() string {
	return fmt.Sprintf("model: field %q has invalid value: %v (%T)", f.Name, f.Value, f.Value)
}

func (ag *AggregateResult) checkFields() error {
	if ag.Version > ResultsVersion {
		return &fieldError{"Version", ag.Version}
	}
	if ag.BuilderInfo == nil {
		return &fieldError{"BuilderInfo", ag.BuilderInfo}
	}
	return nil
}

func (info *BuilderInfo) checkFields() error {
	if info.BuildNumbers == nil {
		return &fieldError{"BuildNumbers", info.BuildNumbers}
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
		return errors.New("uploaded file is missing required num_failures_by_type field")
	}

	res := make(map[string][]int)
	for _, fc := range info.FixableCounts {
		for short, count := range fc {
			long, ok := FailureLongNames[short]
			if !ok {
				return fmt.Errorf("model: unknown key %q", short)
			}
			res[long] = append(res[long], count)
		}
	}

	info.FailuresByType = res
	return nil
}

// AggregateTest represents Tests in a AggregateResult.
type AggregateTest map[string]Node

var _ Node = (AggregateTest)(nil)

func (at AggregateTest) node() {}

// Walk performs a depth-first traversal of the Nodes reachable
// from the receiver, calling fn each time. The Node in fn
// is guaranteed to be either AggregateTest or *AggregateTestLeaf.
// The traversal order may vary across different runs.
func (at AggregateTest) Walk(fn func(key string, node Node)) {
	for key, node := range at {
		switch val := node.(type) {
		case *AggregateTestLeaf:
			fn(key, val)
		case AggregateTest:
			fn(key, val)
			val.Walk(fn)
		}
	}
}

// WalkLeaves is similar to Walk but only calls fn for
// *AggregateTestLeaf.
func (at AggregateTest) WalkLeaves(fn func(key string, leaf *AggregateTestLeaf)) {
	at.Walk(func(key string, node Node) {
		if leaf, ok := node.(*AggregateTestLeaf); ok {
			fn(key, leaf)
		}
	})
}

// MarshalJSON marshals at into JSON.
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

// UnmarshalJSON unmarshals the supplied data into at.
func (at *AggregateTest) UnmarshalJSON(data []byte) error {
	var m map[string]interface{}
	if err := json.Unmarshal(data, &m); err != nil {
		return err
	}
	if at == nil {
		return errors.New("model: UnmarshalJSON: nil *AggregateTest")
	}
	if *at == nil {
		*at = AggregateTest{}
	}
	return at.constructTree(m)
}

// constructTree constructs the tree of Nodes from the supplied map.
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

// isAggregateTestLeaf returns true if the supplied map is likely an
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

func (leaf *AggregateTestLeaf) node() {}

// aggregateTestLeafAux is used to marshal and unmarshal AggregateTestLeaf.
type aggregateTestLeafAux struct {
	Results  []ResultSummary  `json:"results,omitempty"`
	Runtimes []RuntimeSummary `json:"times,omitempty"`
	Expected *string          `json:"expected,omitempty"`
	Bugs     []string         `json:"bugs,omitempty"`
}

// MarshalJSON marshals leaf into JSON.
func (leaf *AggregateTestLeaf) MarshalJSON() ([]byte, error) {
	aux := aggregateTestLeafAux{
		Results:  leaf.Results,
		Runtimes: leaf.Runtimes,
		Bugs:     leaf.Bugs,
	}
	if s := strings.Join(leaf.Expected, " "); len(s) > 0 {
		aux.Expected = &s
	}
	return json.Marshal(&aux)
}

// UnmarshalJSON unmarshals the supplied data into leaf.
func (leaf *AggregateTestLeaf) UnmarshalJSON(data []byte) error {
	var aux aggregateTestLeafAux
	if err := json.Unmarshal(data, &aux); err != nil {
		return err
	}

	leaf.Results = aux.Results
	leaf.Runtimes = aux.Runtimes
	if aux.Expected != nil {
		leaf.Expected = strings.Split(*aux.Expected, " ")
	}
	leaf.Bugs = aux.Bugs

	return nil
}

// defaultFields sets default values for missing/invalid fieldatastore.
func (leaf *AggregateTestLeaf) defaultFields() {
	if len(leaf.Results) == 0 {
		leaf.Results = []ResultSummary{{1, "N"}}
	}
	if len(leaf.Runtimes) == 0 {
		leaf.Runtimes = []RuntimeSummary{{1, 0}}
	}
}

// ResultSummary is the type of test failure and count of how many
// times the running time occured.
type ResultSummary struct {
	Count int
	Type  string
}

// MarshalJSON marshals rs into JSON.
func (rs *ResultSummary) MarshalJSON() ([]byte, error) {
	return json.Marshal([]interface{}{
		rs.Count,
		rs.Type,
	})
}

// UnmarshalJSON unmarshals the provided data into rs.
func (rs *ResultSummary) UnmarshalJSON(data []byte) error {
	var tmp []interface{}
	if err := json.Unmarshal(data, &tmp); err != nil {
		return err
	}
	if len(tmp) != 2 {
		return fmt.Errorf("model: UnmarshalJSON: ResultSummary wrong length: %d, expect: %d", len(tmp), 2)
	}

	count, ok := tmp[0].(float64)
	if !ok {
		return fmt.Errorf("model: UnmarshalJSON: ResultSummary wrong type: %v", tmp)
	}
	rs.Count = int(count)

	rs.Type, ok = tmp[1].(string)
	if !ok {
		return fmt.Errorf("model: UnmarshalJSON: ResultSummary wrong type: %v", tmp)
	}

	return nil
}

// RuntimeSummary is the running time of a test and count of how many
// times the running time occured.
type RuntimeSummary struct {
	Count   int
	Runtime float64
}

// MarshalJSON marshals rs into JSON.
func (rs *RuntimeSummary) MarshalJSON() ([]byte, error) {
	return json.Marshal([]float64{
		float64(rs.Count),
		rs.Runtime,
	})
}

// UnmarshalJSON unmarshals the provided data into rs.
func (rs *RuntimeSummary) UnmarshalJSON(data []byte) error {
	var tmp []float64
	if err := json.Unmarshal(data, &tmp); err != nil {
		return err
	}
	if len(tmp) != 2 {
		return fmt.Errorf("model: UnmarshalJSON: RuntimeSummary wrong length: %d, expect: %d", len(tmp), 2)
	}

	rs.Count = int(tmp[0])
	rs.Runtime = tmp[1]
	return nil
}

var (
	// ErrBuildNumberConflict is returned when the build numbers
	// are the same when merging.
	ErrBuildNumberConflict = errors.New("build number conflict")

	// ErrBuilderNameConflict is returned when the builder names
	// do not match when merging.
	ErrBuilderNameConflict = errors.New("builder name conflict")
)

// Merge merges other into ag.
func (ag *AggregateResult) Merge(other *AggregateResult) error {
	if ag.Builder != other.Builder {
		return ErrBuilderNameConflict
	}
	if ag.BuilderInfo == nil {
		ag.BuilderInfo = &BuilderInfo{}
	}
	ag.Version = ResultsVersion
	return ag.BuilderInfo.Merge(other.BuilderInfo)
}

// Merge merges other into info.
//
// The returned error is ErrBuildNumberConflict when
// other.BuildNumbers[0] already has the latest build number.
func (info *BuilderInfo) Merge(other *BuilderInfo) error {
	if len(info.BuildNumbers) > 0 && len(other.BuildNumbers) > 0 {
		if info.BuildNumbers[0] == other.BuildNumbers[0] {
			return ErrBuildNumberConflict
		}
	}

	info.SecondsEpoch = append(other.SecondsEpoch, info.SecondsEpoch...)
	info.BlinkRevs = append(other.BlinkRevs, info.BlinkRevs...)
	info.BuildNumbers = append(other.BuildNumbers, info.BuildNumbers...)
	info.ChromeRevs = append(other.ChromeRevs, info.ChromeRevs...)

	if info.FailuresByType == nil && other.FailuresByType != nil {
		info.FailuresByType = make(map[string][]int)
	}
	for k, v := range other.FailuresByType {
		info.FailuresByType[k] = append(v, info.FailuresByType[k]...)
	}

	info.FailureMap = FailureLongNames

	if info.Tests == nil {
		info.Tests = AggregateTest{}
	}

	info.Tests.WalkLeaves(func(_ string, leaf *AggregateTestLeaf) {
		leaf.Expected = nil
		leaf.Bugs = nil
	})

	return info.Tests.Merge(other.Tests)
}

// Merge merges other into at.
func (at *AggregateTest) Merge(other AggregateTest) error {
	// Shallow copy but OK. We take care to not modify otherCopy
	// values; instead always create new objects
	// and assign to otherCopy[key].
	otherCopy := make(AggregateTest, len(other))
	for k, v := range other {
		otherCopy[k] = v
	}

	for k, v := range *at {
		if _, ok := otherCopy[k]; !ok {
			switch v.(type) {
			case *AggregateTestLeaf:
				l := &AggregateTestLeaf{}
				l.defaultFields()
				otherCopy[k] = l
			case AggregateTest:
				otherCopy[k] = AggregateTest{}
			}
		}
	}

	for k, v := range otherCopy {
		// Key does not exist: assign entire subtree.
		if _, ok := (*at)[k]; !ok {
			if *at == nil {
				*at = AggregateTest{}
			}
			(*at)[k] = v
			continue
		}

		// Leaf node.
		if leaf1, ok := (*at)[k].(*AggregateTestLeaf); ok {
			leaf2, ok := v.(*AggregateTestLeaf)
			if !ok {
				return fmt.Errorf("model: Merge: expected *AggregateTestLeaf, but got: %#v", v)
			}
			if err := leaf1.Merge(leaf2); err != nil {
				return err
			}
			continue
		}

		// Not leaf node: merge subtree recursively.
		at1, ok := (*at)[k].(AggregateTest)
		if !ok {
			return fmt.Errorf("model: Merge (*at)[%s]: expected AggregateTest, but got: %#v", k, (*at)[k])
		}
		at2, ok := v.(AggregateTest)
		if !ok {
			return fmt.Errorf("model: Merge (v): expected AggregateTest, but got: %#v", v)
		}
		if err := at1.Merge(at2); err != nil {
			return err
		}
	}

	return nil
}

// Merge merges other into leaf.
func (leaf *AggregateTestLeaf) Merge(other *AggregateTestLeaf) error {
	// Bugs and Expected should come from from other only.
	leaf.Bugs = other.Bugs
	if len(other.Expected) == 1 && other.Expected[0] != "PASS" {
		leaf.Expected = other.Expected
	}

	for _, r := range other.Results {
		if len(leaf.Results) > 0 && r.Type == leaf.Results[0].Type {
			leaf.Results[0].Count += r.Count
		} else {
			leaf.Results = append([]ResultSummary{r}, leaf.Results...)
		}
	}

	for _, r := range other.Runtimes {
		if len(leaf.Runtimes) > 0 && r.Runtime == leaf.Runtimes[0].Runtime {
			leaf.Runtimes[0].Count += r.Count
		} else {
			leaf.Runtimes = append([]RuntimeSummary{r}, leaf.Runtimes...)
		}
	}

	return nil
}

const (
	// ResultsSize is the size that "results.json" should be trimmed to.
	ResultsSize = 500

	// ResultsSmallSize is the size that "results_small.json" should
	// be trimmed to.
	ResultsSmallSize = 100

	runtimeThresholdNormal float64 = 3 // In secondatastore.
	runtimeThresholdDebug  float64 = 9 // In secondatastore.
)

func isDebugBuilder(builder string) bool {
	for _, s := range []string{"debug", "dbg"} {
		if strings.Contains(strings.ToLower(builder), s) {
			return true
		}
	}
	return false
}

// Trim trims ag's fields to the specified size.
func (ag *AggregateResult) Trim(size int) error {
	t := runtimeThresholdNormal

	if isDebugBuilder(ag.Builder) {
		t = runtimeThresholdDebug
	}

	ag.SecondsEpoch = ag.SecondsEpoch[:min(size, len(ag.SecondsEpoch))]
	ag.BlinkRevs = ag.BlinkRevs[:min(size, len(ag.BlinkRevs))]
	ag.ChromeRevs = ag.ChromeRevs[:min(size, len(ag.ChromeRevs))]
	ag.BuildNumbers = ag.BuildNumbers[:min(size, len(ag.BuildNumbers))]

	return ag.Tests.trim(size, t)
}

func (at AggregateTest) trim(size int, threshold float64) error {
	for k, v := range at {
		if leaf, ok := v.(*AggregateTestLeaf); ok {
			leaf.trim(size)
			if leaf.shouldDelete(threshold) {
				delete(at, k)
			}
			continue
		}

		child, ok := v.(AggregateTest)
		if !ok {
			return errors.New("model: trim: expected AggregateTest")
		}
		if err := child.trim(size, threshold); err != nil {
			return err
		}
		if len(child) == 0 {
			delete(at, k)
		}
	}
	return nil
}

func (leaf *AggregateTestLeaf) trim(size int) {
	n := 0

	for i, r := range leaf.Results {
		leaf.Results[i].Count = min(r.Count, size)
		n += r.Count
		if n >= size {
			leaf.Results = leaf.Results[:i+1]
			break
		}
	}

	n = 0

	for i, r := range leaf.Runtimes {
		leaf.Runtimes[i].Count = min(r.Count, size)
		n += r.Count
		if n >= size {
			leaf.Runtimes = leaf.Runtimes[:i+1]
			break
		}
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

var deletableTypes = map[string]bool{"P": true, "N": true, "Y": true}

func (leaf *AggregateTestLeaf) shouldDelete(threshold float64) bool {
	if len(leaf.Expected) == 1 && leaf.Expected[0] != "PASS" {
		return false
	}
	if leaf.Bugs != nil {
		return false
	}

	for _, r := range leaf.Results {
		if !deletableTypes[r.Type] {
			return false
		}
	}
	for _, r := range leaf.Runtimes {
		if r.Runtime >= threshold {
			return false
		}
	}

	return true
}
