// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"flag"
	"fmt"
)

// TODO(akeshet): Promote this to a shared library.

// MultiArg is a flag.Value implementation for an underling []string, that
// can be specified multiple times on the command line.
func MultiArg(output *[]string) flag.Value {
	return &multiArg{
		vals: output,
	}
}

type multiArg struct {
	vals *[]string
}

func (m *multiArg) Set(s string) error {
	*m.vals = append(*m.vals, s)
	return nil
}

func (m *multiArg) String() string {
	return fmt.Sprintf("%v", m.vals)
}
