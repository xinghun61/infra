// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package inventory implements Skylab inventory stuff.
package inventory

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"go.chromium.org/luci/common/errors"
)

// ReadSymlink dereferences the symlink pointing to the data
// directory.  This symlink can be missing for small amounts of time
// on the servers, but once the symlink has been dereferenced, the
// target directory is guaranteed to exist for ~15 minutes.
func ReadSymlink(p string) (string, error) {
	const attempts = 4
	sleep := 10 * time.Millisecond
	var errs []error
	for i := 0; i < attempts; i++ {
		t, err := filepath.EvalSymlinks(p)
		if err != nil {
			errs = append(errs, err)
			time.Sleep(sleep)
			sleep *= 2
			continue
		}
		return t, nil
	}
	err := errors.MultiError(errs)
	return "", errors.Annotate(err, "read inventory symlink %s: too many tries", p).Err()
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

// SortLabels takes a SchedulableLabels and destructively canonicalizes it.
// If two SchedulableLabels are equal post-canonicalization,
// then they represent the "same" thing.
// An arbitrary SchedulableLabels is not necessarily in canonical form.
// For example, the VideoAcceleration labels are not guaranteed to be sorted.
// In order to use proto.Equal, we must canonicalize first.
func SortLabels(labels *SchedulableLabels) {
	{
		p := labels.CriticalPools
		sort.Slice(p, func(i, j int) bool {
			return p[i] < p[j]
		})
	}
	{
		abi := labels.CtsAbi
		sort.Slice(abi, func(i, j int) bool {
			return abi[i] < abi[j]
		})
	}
	{
		cpu := labels.CtsCpu
		sort.Slice(cpu, func(i, j int) bool {
			return cpu[i] < cpu[j]
		})
	}
	{
		p := labels.SelfServePools
		sort.Slice(p, func(i, j int) bool {
			return p[i] < p[j]
		})
	}
	{
		v := labels.Variant
		sort.Slice(v, func(i, j int) bool {
			return v[i] < v[j]
		})
	}
	{
		v := labels.Capabilities.VideoAcceleration
		sort.Slice(v, func(i, j int) bool {
			return v[i] < v[j]
		})
	}
}
