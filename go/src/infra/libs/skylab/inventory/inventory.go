// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package inventory implements Skylab inventory stuff.
package inventory

import (
	"io/ioutil"
	"os"
	"path/filepath"

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
	if err := proto.UnmarshalText(string(b), &lab); err != nil {
		return nil, errors.Annotate(err, "load lab inventory %s", dataDir).Err()
	}
	return &lab, nil

}

// WriteLab writes lab inventory information to the inventory data directory.
func WriteLab(lab *Lab, dataDir string) error {
	f, err := ioutil.TempFile(dataDir, labFilename)
	if err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	defer func() {
		if f != nil {
			_ = os.Remove(f.Name())
		}
	}()
	defer f.Close()
	m := proto.TextMarshaler{}
	if err := m.Marshal(f, lab); err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	if err := os.Rename(f.Name(), filepath.Join(dataDir, labFilename)); err != nil {
		return errors.Annotate(err, "write lab inventory %s", dataDir).Err()
	}
	f = nil
	return nil
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

// WriteInfrastructure writes infrastructure information to the inventory data directory.
func WriteInfrastructure(infrastructure *Infrastructure, dataDir string) error {
	f, err := ioutil.TempFile(dataDir, infraFilename)
	if err != nil {
		return errors.Annotate(err, "write infrastructure inventory %s", dataDir).Err()
	}
	defer func() {
		if f != nil {
			_ = os.Remove(f.Name())
		}
	}()
	defer f.Close()
	m := proto.TextMarshaler{}
	if err := m.Marshal(f, infrastructure); err != nil {
		return errors.Annotate(err, "write infrastructure inventory %s", dataDir).Err()
	}
	if err := f.Close(); err != nil {
		return errors.Annotate(err, "write infrastructure inventory %s", dataDir).Err()
	}
	if err := os.Rename(f.Name(), filepath.Join(dataDir, infraFilename)); err != nil {
		return errors.Annotate(err, "write infrastructure inventory %s", dataDir).Err()
	}
	f = nil
	return nil
}
