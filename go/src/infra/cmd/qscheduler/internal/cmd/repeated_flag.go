// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"flag"
	"fmt"
	"strconv"
)

// TODO(akeshet): Promote this to a shared library.

// MultiString is a flag.Value implementation for an underling []string, that
// can be specified multiple times on the command line.
func MultiString(output *[]string) flag.Value {
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

// MultiFloat is a flag.Value implementation for an underling []float64, that
// can be specified multiple times on the command line.
func MultiFloat(output *[]float64) flag.Value {
	return &multiFloat{
		vals: output,
	}
}

type multiFloat struct {
	vals *[]float64
}

func (m *multiFloat) Set(s string) error {
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return err
	}
	*m.vals = append(*m.vals, f)
	return nil
}

func (m *multiFloat) String() string {
	return fmt.Sprintf("%v", m.vals)
}
