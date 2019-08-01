// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"os"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
	"go.chromium.org/luci/common/errors"
)

// readJSONPb reads a JSON string from inFile and unpacks it as a proto.
// Unexpected fields are ignored.
func readJSONPb(inFile string, payload proto.Message) error {
	r, err := os.Open(inFile)
	if err != nil {
		return errors.Annotate(err, "read JSON pb").Err()
	}
	defer r.Close()

	unmarshaler := jsonpb.Unmarshaler{AllowUnknownFields: true}
	if err := unmarshaler.Unmarshal(r, payload); err != nil {
		return errors.Annotate(err, "read JSON pb").Err()
	}
	return nil
}

// writeJSONPb writes a JSON encoded proto to outFile.
func writeJSONPb(outFile string, payload proto.Message) error {
	w, err := os.Create(outFile)
	if err != nil {
		return errors.Annotate(err, "write JSON pb").Err()
	}
	defer w.Close()

	marshaler := jsonpb.Marshaler{}
	if err := marshaler.Marshal(w, payload); err != nil {
		return errors.Annotate(err, "write JSON pb").Err()
	}
	return nil
}
