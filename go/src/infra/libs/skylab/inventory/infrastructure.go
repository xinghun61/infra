// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package inventory

import (
	"bytes"
	"io/ioutil"
	"path/filepath"

	proto "github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"
)

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
