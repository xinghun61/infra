// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state

import (
	"encoding/base64"
	"strings"

	"github.com/golang/protobuf/proto"

	"go.chromium.org/luci/common/errors"
)

// FromENV loads the contents of ws from an encoded environment variable.
func (st *State) FromENV(v string) error {
	st.Reset()

	v = strings.TrimSpace(v)
	if v == "" {
		return nil
	}

	d, err := base64.StdEncoding.DecodeString(v)
	if err != nil {
		return errors.Annotate(err, "failed to decode base 64").Err()
	}

	if err := proto.Unmarshal(d, st); err != nil {
		return errors.Annotate(err, "failed to unmarshal state").Err()
	}

	return nil
}

// ToENV constructs the exported environment variable form of the wrapper.
func (st *State) ToENV() string {
	d, err := proto.Marshal(st)
	if err != nil {
		panic(errors.Annotate(err, "failed to marshal wrapper state").Err())
	}
	return base64.StdEncoding.EncodeToString(d)
}
