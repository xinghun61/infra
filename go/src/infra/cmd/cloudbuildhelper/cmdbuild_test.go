// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"io/ioutil"
	"testing"

	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
	"infra/cmd/cloudbuildhelper/storage"

	. "github.com/smartystreets/goconvey/convey"
)

func TestBuild(t *testing.T) {
	t.Parallel()

	ctx := context.Background()
	store := newStorageImplMock()
	fs, digest := prepFileSet()

	Convey("Never seen before tarball", t, func() {
		err := remoteBuild(ctx, remoteBuildParams{
			Manifest: &manifest.Manifest{Name: "test-name"},
			Out:      fs,
			Store:    store,
		})
		So(err, ShouldBeNil)

		// Uploaded the file.
		obj, err := store.Check(ctx, fmt.Sprintf("test-name/%s.tar.gz", digest))
		So(err, ShouldBeNil)
		So(obj, ShouldNotBeNil)
		So(obj.Generation, ShouldEqual, 1)
	})

	Convey("Already uploaded tarball", t, func() {
		store.plant(fmt.Sprintf("test-name/%s.tar.gz", digest), 12345)

		err := remoteBuild(ctx, remoteBuildParams{
			Manifest: &manifest.Manifest{Name: "test-name"},
			Out:      fs,
			Store:    store,
		})
		So(err, ShouldBeNil)

		// Didn't overwrite the existing file.
		obj, err := store.Check(ctx, fmt.Sprintf("test-name/%s.tar.gz", digest))
		So(err, ShouldBeNil)
		So(obj, ShouldNotBeNil)
		So(obj.Generation, ShouldEqual, 12345)
	})
}

func prepFileSet() (fs *fileset.Set, digest string) {
	fs = &fileset.Set{}

	fs.AddFromMemory("Dockerfile", []byte("boo-boo-boo"), nil)
	fs.AddFromMemory("dir/something", []byte("ba-ba-ba"), nil)

	h := sha256.New()
	if err := fs.ToTarGz(h); err != nil {
		panic(err)
	}
	digest = hex.EncodeToString(h.Sum(nil))
	return
}

type objBlob struct {
	storage.Object
	Blob []byte
}

type storageImplMock struct {
	gen   int64
	blobs map[string]objBlob
}

func newStorageImplMock() *storageImplMock {
	return &storageImplMock{
		blobs: make(map[string]objBlob, 0),
	}
}

func (s *storageImplMock) plant(name string, gen int64) {
	s.blobs[name] = objBlob{
		Object: storage.Object{Name: name, Generation: gen},
	}
}

func (s *storageImplMock) Check(ctx context.Context, name string) (*storage.Object, error) {
	itm, ok := s.blobs[name]
	if !ok {
		return nil, nil
	}
	return &itm.Object, nil
}

func (s *storageImplMock) Upload(ctx context.Context, name, digest string, r io.Reader) (*storage.Object, error) {
	h := sha256.New()
	blob, err := ioutil.ReadAll(io.TeeReader(r, h))
	if err != nil {
		return nil, err
	}
	if d := hex.EncodeToString(h.Sum(nil)); d != digest {
		return nil, fmt.Errorf("got digest %q, expecting %q", d, digest)
	}

	s.gen++

	obj := storage.Object{
		Name:       name,
		Generation: s.gen,
	}

	s.blobs[name] = objBlob{
		Object: obj,
		Blob:   blob,
	}
	return &obj, nil
}
