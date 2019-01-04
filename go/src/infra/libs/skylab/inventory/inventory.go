// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package inventory implements Skylab inventory stuff.
package inventory

import (
	"bytes"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"
)

const labFilename = "lab.textpb"

// LoadLab loads lab inventory information from the inventory data directory.
func LoadLab(dataDir string) (*Lab, error) {
	b, err := ioutil.ReadFile(filepath.Join(dataDir, labFilename))
	if err != nil {
		return nil, errors.Annotate(err, "load lab inventory %s", dataDir).Err()
	}
	lab := Lab{}
	if err := LoadLabFromString(string(b), &lab); err != nil {
		return nil, errors.Annotate(err, "load lab inventory %s", dataDir).Err()
	}
	return &lab, nil

}

// LoadLabFromString loads lab inventory information from the given string.
func LoadLabFromString(text string, lab *Lab) error {
	return proto.UnmarshalText(text, lab)
}

// WriteLab writes lab inventory information to the inventory data directory.
//
// WriteLab serializes the proto in a format that can be loaded from both
// golang and python protobuf libraries.
func WriteLab(lab *Lab, dataDir string) error {
	labStr, err := WriteLabToString(lab)
	if err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	// rewriteMarshaledTextProtoForPython is a hacky translation of protos to
	// python library friendly format. At least make sure we can load the proto
	// back in to catch obvious corruption.
	var relab Lab
	if err := LoadLabFromString(labStr, &relab); err != nil {
		return errors.Annotate(err, "validate lab inventory written to %s", dataDir).Err()
	}
	if err := oneShotWriteFile(dataDir, labFilename, labStr); err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	return nil
}

// WriteLabToString marshals lab inventory information into a string.
func WriteLabToString(lab *Lab) (string, error) {
	lab = proto.Clone(lab).(*Lab)
	if lab != nil {
		sortLab(lab)
	}
	m := proto.TextMarshaler{}
	var b bytes.Buffer
	err := m.Marshal(&b, lab)
	return string(rewriteMarshaledTextProtoForPython(b.Bytes())), err
}

const infraFilename = "server_db.textpb"

// LoadInfrastructure loads infrastructure information from the inventory data directory.
func LoadInfrastructure(dataDir string) (*Infrastructure, error) {
	b, err := ioutil.ReadFile(filepath.Join(dataDir, infraFilename))
	if err != nil {
		return nil, errors.Annotate(err, "load infrastructure inventory %s", dataDir).Err()
	}
	infrastructure := Infrastructure{}
	if err := proto.UnmarshalText(string(b), &infrastructure); err != nil {
		return nil, errors.Annotate(err, "load infrastructure inventory %s", dataDir).Err()
	}
	return &infrastructure, nil
}

// LoadInfrastructureFromString loads infrastructure inventory information from the given string.
func LoadInfrastructureFromString(text string, infra *Infrastructure) error {
	return proto.UnmarshalText(text, infra)
}

// WriteInfrastructure writes infrastructure information to the inventory data directory.
func WriteInfrastructure(infrastructure *Infrastructure, dataDir string) error {
	m := proto.TextMarshaler{}
	var b bytes.Buffer
	if err := m.Marshal(&b, infrastructure); err != nil {
		return errors.Annotate(err, "write infrastructure inventory %s", dataDir).Err()
	}
	text := string(rewriteMarshaledTextProtoForPython(b.Bytes()))
	return oneShotWriteFile(dataDir, infraFilename, text)
}

// WriteInfrastructureToString marshals infrastructure inventory information into a string.
func WriteInfrastructureToString(infra *Infrastructure) (string, error) {
	infra = proto.Clone(infra).(*Infrastructure)

	// TODO(akeshet): Add a sortInfra() to deep sort infra prior to writing
	// (similar to sortLab usage in WriteLabToString above).

	m := proto.TextMarshaler{}
	var b bytes.Buffer
	err := m.Marshal(&b, infra)
	return string(rewriteMarshaledTextProtoForPython(b.Bytes())), err
}

var suffixReplacements = map[string]string{
	": <": " {",
	">":   "}",
}

// rewriteMarshaledTextProtoForPython rewrites the serialized prototext similar
// to how python proto library output format.
//
// prototext format is not unique. Go's proto serializer and python's proto
// serializer output slightly different formats. They can each parse the other
// library's output. Since our tools are currently split between python and go,
// the different output formats creates trivial diffs each time a tool from a
// different language is used. This function is a hacky post-processing step to
// make the serialized prototext look similar to what the python library would
// output.
func rewriteMarshaledTextProtoForPython(data []byte) []byte {
	// python proto library does not (de)serialize None.
	// Promote nil value to an empty proto.
	if string(data) == "<nil>" {
		return []byte("")
	}

	ls := strings.Split(string(data), "\n")
	rls := make([]string, 0, len(ls))
	for _, l := range ls {
		for k, v := range suffixReplacements {
			if strings.HasSuffix(l, k) {
				l = strings.TrimSuffix(l, k)
				l = fmt.Sprintf("%s%s", l, v)
			}
		}
		rls = append(rls, l)
	}
	return []byte(strings.Join(rls, "\n"))
}

// oneShotWriteFile writes data to dataDir/fileName.
//
// This function ensures that the original file is left unmodified in case of
// write errors.
func oneShotWriteFile(dataDir, fileName string, data string) error {
	fp := filepath.Join(dataDir, fileName)
	f, err := ioutil.TempFile(dataDir, fileName)
	if err != nil {
		return errors.Annotate(err, "write inventory %s", fp).Err()
	}
	defer func() {
		if f != nil {
			_ = os.Remove(f.Name())
		}
	}()
	defer f.Close()
	if err := ioutil.WriteFile(f.Name(), []byte(data), 0600); err != nil {
		return errors.Annotate(err, "write inventory %s", fp).Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "write inventory %s", fp).Err()
	}
	if err := os.Rename(f.Name(), fp); err != nil {
		return errors.Annotate(err, "write inventory %s", fp).Err()
	}
	f = nil
	return nil
}

// sortLab deep sorts lab in place.
func sortLab(lab *Lab) {
	for _, d := range lab.Duts {
		sortCommonDeviceSpecs(d.GetCommon())
	}
	sort.SliceStable(lab.Duts, func(i, j int) bool {
		return strings.ToLower(lab.Duts[i].GetCommon().GetHostname()) <
			strings.ToLower(lab.Duts[j].GetCommon().GetHostname())
	})

	for _, d := range lab.ServoHosts {
		sortCommonDeviceSpecs(d.GetCommon())
	}
	sort.SliceStable(lab.ServoHosts, func(i, j int) bool {
		return strings.ToLower(lab.ServoHosts[i].GetCommon().GetHostname()) <
			strings.ToLower(lab.ServoHosts[j].GetCommon().GetHostname())
	})

	for _, d := range lab.Chamelons {
		sortCommonDeviceSpecs(d.GetCommon())
	}
	sort.SliceStable(lab.Chamelons, func(i, j int) bool {
		return strings.ToLower(lab.Chamelons[i].GetCommon().GetHostname()) <
			strings.ToLower(lab.Chamelons[j].GetCommon().GetHostname())
	})

	sort.SliceStable(lab.ServoHostConnections, func(i, j int) bool {
		x := lab.ServoHostConnections[i]
		y := lab.ServoHostConnections[j]
		switch {
		case x.GetServoHostId() < y.GetServoHostId():
			return true
		case x.GetServoHostId() > y.GetServoHostId():
			return false
		default:
			// Check next key
		}
		switch {
		case x.GetDutId() < y.GetDutId():
			return true
		case x.GetDutId() > y.GetDutId():
			return false
		default:
			// Check next key
		}
		return x.GetServoPort() < y.GetServoPort()
	})

	// ChameleonConnections are unused and schema is untenable.
	// Sort not implemented yet.
}

func sortCommonDeviceSpecs(c *CommonDeviceSpecs) {
	if c == nil {
		return
	}

	sort.SliceStable(c.DeviceLocks, func(i, j int) bool {
		return c.DeviceLocks[i].GetId() < c.DeviceLocks[j].GetId()
	})
	sort.SliceStable(c.Attributes, func(i, j int) bool {
		return strings.ToLower(c.Attributes[i].GetKey()) < strings.ToLower(c.Attributes[j].GetKey())
	})

	sl := c.Labels
	if sl != nil {
		sort.SliceStable(sl.CriticalPools, func(i, j int) bool {
			return sl.CriticalPools[i] < sl.CriticalPools[j]
		})
		sort.Strings(sl.SelfServePools)
	}
}
