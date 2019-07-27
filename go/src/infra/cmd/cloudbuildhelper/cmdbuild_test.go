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
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/cmd/cloudbuildhelper/cloudbuild"
	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
	"infra/cmd/cloudbuildhelper/storage"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

const (
	testTargetName   = "test-name"
	testBucketName   = "test-bucket"
	testRegistryName = "fake.example.com/registry"

	testImageName = testRegistryName + "/" + testTargetName
)

func TestBuild(t *testing.T) {
	t.Parallel()

	Convey("With mocks", t, func() {
		ctx, tc := testclock.UseTime(context.Background(), testclock.TestRecentTimeUTC)
		tc.SetTimerCallback(func(d time.Duration, t clock.Timer) {
			if testclock.HasTags(t, "sleep-timer") {
				tc.Add(d)
			}
		})
		ctx, _ = clock.WithTimeout(ctx, 20*time.Minute) // don't hang forever

		store := newStorageImplMock()
		builder := newBuilderImplMock()
		fs, digest := prepFileSet()

		var (
			// Path relative to the storage root.
			testTarballPath = fmt.Sprintf("%s/%s.tar.gz", testTargetName, digest)
			// Where we drops the tarball, excluding "#<generation>" suffix.
			testTarballURL = fmt.Sprintf("gs://%s/%s/%s.tar.gz", testBucketName, testTargetName, digest)
		)

		builder.outputDigests = func(img string) string {
			So(img, ShouldEqual, testImageName+":cbh")
			return "sha256:totally-legit-hash"
		}

		Convey("Never seen before tarball", func() {
			builder.provenance = func(gs string) string {
				So(gs, ShouldEqual, testTarballURL+"#1") // used first gen
				return digest                            // got its digest correctly
			}

			res, err := remoteBuild(ctx, remoteBuildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Out:      fs,
				Registry: testRegistryName,
				Store:    store,
				Builder:  builder,
			})
			So(err, ShouldBeNil)

			// Uploaded the file.
			obj, err := store.Check(ctx, testTarballPath)
			So(err, ShouldBeNil)
			So(obj.String(), ShouldEqual, testTarballURL+"#1") // uploaded the first gen

			// Used Cloud Build.
			So(res, ShouldResemble, &remoteBuildResult{
				Image:  testImageName,
				Digest: "sha256:totally-legit-hash",
			})
		})

		Convey("Already uploaded tarball", func() {
			// Pretend we already have generation 12345 in the store.
			store.plant(testTarballPath, 12345)

			builder.provenance = func(gs string) string {
				So(gs, ShouldEqual, testTarballURL+"#12345") // used this gen
				return digest                                // got its digest correctly
			}

			res, err := remoteBuild(ctx, remoteBuildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Out:      fs,
				Registry: testRegistryName,
				Store:    store,
				Builder:  builder,
			})
			So(err, ShouldBeNil)

			// Didn't overwrite the existing file.
			obj, err := store.Check(ctx, testTarballPath)
			So(err, ShouldBeNil)
			So(obj.String(), ShouldEqual, testTarballURL+"#12345") // still same gen

			// Used Cloud Build.
			So(res, ShouldResemble, &remoteBuildResult{
				Image:  testImageName,
				Digest: "sha256:totally-legit-hash",
			})
		})

		Convey("No registry is set => nothing is uploaded", func() {
			builder.provenance = func(gs string) string {
				So(gs, ShouldEqual, testTarballURL+"#1") // used first gen
				return digest                            // got its digest correctly
			}

			res, err := remoteBuild(ctx, remoteBuildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Out:      fs,
				Store:    store,
				Builder:  builder,
			})
			So(err, ShouldBeNil)

			// Uploaded the file.
			obj, err := store.Check(ctx, testTarballPath)
			So(err, ShouldBeNil)
			So(obj.String(), ShouldEqual, testTarballURL+"#1") // uploaded the first gen

			// Did NOT produce any image.
			So(res, ShouldResemble, &remoteBuildResult{})
		})

		Convey("Cloud Build build failure", func() {
			builder.finalStatus = cloudbuild.StatusFailure
			_, err := remoteBuild(ctx, remoteBuildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Out:      fs,
				Registry: testRegistryName,
				Store:    store,
				Builder:  builder,
			})
			So(err, ShouldErrLike, "build failed, see its logs")
		})

		Convey("Cloud Build API errors", func() {
			builder.checkCallback = func(b *runningBuild) error {
				return fmt.Errorf("boom")
			}
			_, err := remoteBuild(ctx, remoteBuildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Out:      fs,
				Registry: testRegistryName,
				Store:    store,
				Builder:  builder,
			})
			So(err, ShouldErrLike, "when waiting for the build to finish: too many errors, the last one: boom")
		})
	})
}

////////////////////////////////////////////////////////////////////////////////

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

////////////////////////////////////////////////////////////////////////////////

type storageImplMock struct {
	gen   int64
	blobs map[string]objBlob
}

type objBlob struct {
	storage.Object
	Blob []byte
}

func newStorageImplMock() *storageImplMock {
	return &storageImplMock{
		blobs: make(map[string]objBlob, 0),
	}
}

func (s *storageImplMock) plant(name string, gen int64) {
	s.blobs[name] = objBlob{
		Object: storage.Object{
			Bucket:     testBucketName,
			Name:       name,
			Generation: gen,
		},
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
		Bucket:     testBucketName,
		Name:       name,
		Generation: s.gen,
	}

	s.blobs[name] = objBlob{
		Object: obj,
		Blob:   blob,
	}
	return &obj, nil
}

////////////////////////////////////////////////////////////////////////////////

type builderImplMock struct {
	// Can be touched.
	checkCallback func(b *runningBuild) error
	finalStatus   cloudbuild.Status
	provenance    func(gs string) string  // gs://.... => SHA256
	outputDigests func(img string) string // full image name => "sha256:..."

	// Shouldn't be touched.
	nextID int64
	builds map[string]runningBuild
}

type runningBuild struct {
	cloudbuild.Build
	Request cloudbuild.Request
}

func newBuilderImplMock() *builderImplMock {
	bld := &builderImplMock{
		builds:        make(map[string]runningBuild, 0),
		finalStatus:   cloudbuild.StatusSuccess,
		provenance:    func(string) string { return "" },
		outputDigests: func(string) string { return "" },
	}

	// By default just advance the build through the stages.
	bld.checkCallback = func(b *runningBuild) error {
		switch b.Status {
		case cloudbuild.StatusQueued:
			b.Status = cloudbuild.StatusWorking
		case cloudbuild.StatusWorking:
			b.Status = bld.finalStatus
			if b.Status == cloudbuild.StatusSuccess {
				b.InputHashes = map[string]string{
					b.Request.Source.String(): bld.provenance(b.Request.Source.String()),
				}
				b.OutputImage = b.Request.Image
				if b.Request.Image != "" {
					b.OutputDigest = bld.outputDigests(b.Request.Image)
				}
			}
		}
		return nil
	}

	return bld
}

func (b *builderImplMock) Trigger(ctx context.Context, r cloudbuild.Request) (*cloudbuild.Build, error) {
	b.nextID++
	build := cloudbuild.Build{
		ID:     fmt.Sprintf("b-%d", b.nextID),
		Status: cloudbuild.StatusQueued,
	}
	b.builds[build.ID] = runningBuild{
		Build:   build,
		Request: r,
	}
	return &build, nil
}

func (b *builderImplMock) Check(ctx context.Context, bid string) (*cloudbuild.Build, error) {
	build, ok := b.builds[bid]
	if !ok {
		return nil, fmt.Errorf("no build %q", bid)
	}
	if err := b.checkCallback(&build); err != nil {
		return nil, err
	}
	b.builds[bid] = build
	return &build.Build, nil
}
