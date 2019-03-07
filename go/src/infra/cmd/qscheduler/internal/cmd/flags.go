// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"errors"
	"fmt"
	"strconv"
)

type nullableFloat32 struct {
	val **float32
}

// nullableFloat32Value returns a flags.Value implementation that allows
// setting a (nullable) float32.
func nullableFloat32Value(dest **float32) nullableFloat32 {
	return nullableFloat32{dest}
}

func (f nullableFloat32) Set(val string) error {
	if *f.val != nil {
		return errors.New("value already set")
	}
	v, err := strconv.ParseFloat(val, 32)
	if err != nil {
		return err
	}
	v32 := float32(v)
	*f.val = &v32
	return nil
}

func (f nullableFloat32) String() string {
	if f.val == nil || *f.val == nil {
		return "unset"
	}
	return fmt.Sprintf("%f", **f.val)
}

type nullableInt32 struct {
	val **int32
}

// nullableFloat32Value returns a flags.Value implementation that allows
// setting a (nullable) int32.
func nullableInt32Value(dest **int32) nullableInt32 {
	return nullableInt32{dest}
}

func (f nullableInt32) Set(val string) error {
	if *f.val != nil {
		return errors.New("value already set")
	}
	v, err := strconv.ParseInt(val, 10, 32)
	if err != nil {
		return err
	}
	v32 := int32(v)
	*f.val = &v32
	return nil
}

func (f nullableInt32) String() string {
	if f.val == nil || *f.val == nil {
		return "unset"
	}
	return fmt.Sprintf("%d", **f.val)
}

type nullableBool struct {
	val **bool
}

// nullableBoolValue returns a flags.Value implementation that allows
// setting a (nullable) bool.
func nullableBoolValue(dest **bool) nullableBool {
	return nullableBool{dest}
}

func (f nullableBool) Set(val string) error {
	if *f.val != nil {
		return errors.New("value already set")
	}
	v, err := strconv.ParseBool(val)
	if err != nil {
		return err
	}
	*f.val = &v
	return nil
}

func (f nullableBool) String() string {
	if f.val == nil || *f.val == nil {
		return "unset"
	}
	return strconv.FormatBool(**f.val)
}
