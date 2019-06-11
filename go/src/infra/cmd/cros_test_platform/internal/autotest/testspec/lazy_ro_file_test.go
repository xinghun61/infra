// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"io/ioutil"
	"path/filepath"
	"testing"
)

func TestLazyROFileSimpleRead(t *testing.T) {
	d, cleanup := createTempDirOrDie(t)
	defer cleanup()
	p := filepath.Join(d, "pleaseBeLazy")
	want := "some random text"
	writeFileOrDie(p, want)
	got, err := ioutil.ReadAll(openROLazy(p))
	if err != nil {
		t.Fatalf("read lazy file: %s", err)
	}
	if string(got) != want {
		t.Errorf("Content mismatch, got: |%s|, want |%s|", string(got), want)
	}

}

func writeFileOrDie(path, content string) {
	if err := ioutil.WriteFile(path, []byte(content), 0644); err != nil {
		panic(err)
	}
}
