// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"bytes"
	"io/ioutil"
	"path/filepath"
	"sort"
	"strings"

	proto "github.com/golang/protobuf/proto"
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
	sortSchedulableLabels(c.Labels)
}

func sortSchedulableLabels(sl *SchedulableLabels) {
	if sl == nil {
		return
	}

	sort.SliceStable(sl.CtsAbi, func(i, j int) bool {
		return sl.CtsAbi[i] < sl.CtsAbi[j]
	})
	sort.SliceStable(sl.CtsCpu, func(i, j int) bool {
		return sl.CtsCpu[i] < sl.CtsCpu[j]
	})
	sort.SliceStable(sl.CriticalPools, func(i, j int) bool {
		return sl.CriticalPools[i] < sl.CriticalPools[j]
	})
	sort.Strings(sl.SelfServePools)
	sort.Strings(sl.Variant)

	if sl.TestCoverageHints != nil {
		h := sl.TestCoverageHints
		sort.SliceStable(h.CtsSparse, func(i, j int) bool {
			return h.CtsSparse[i] < h.CtsSparse[j]
		})
	}

	if sl.Capabilities != nil {
		c := sl.Capabilities
		sort.SliceStable(c.VideoAcceleration, func(i, j int) bool {
			return c.VideoAcceleration[i] < c.VideoAcceleration[j]
		})
	}
}
