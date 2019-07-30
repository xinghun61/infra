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
	"strings"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/clock/testclock"

	"infra/cmd/cloudbuildhelper/cloudbuild"
	"infra/cmd/cloudbuildhelper/fileset"
	"infra/cmd/cloudbuildhelper/manifest"
	"infra/cmd/cloudbuildhelper/registry"
	"infra/cmd/cloudbuildhelper/storage"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

const (
	testTargetName   = "test-name"
	testBucketName   = "test-bucket"
	testRegistryName = "fake.example.com/registry"
	testDigest       = "sha256:totally-legit-hash"
	testTagName      = "canonical-tag"

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
		registry := newRegistryImplMock()
		builder := newBuilderImplMock(registry)
		fs, digest := prepFileSet()

		var (
			// Path relative to the storage root.
			testTarballPath = fmt.Sprintf("%s/%s.tar.gz", testTargetName, digest)
			// Where we drops the tarball, excluding "#<generation>" suffix.
			testTarballURL = fmt.Sprintf("gs://%s/%s/%s.tar.gz", testBucketName, testTargetName, digest)
		)

		builder.outputDigests = func(img string) string {
			So(img, ShouldEqual, testImageName+":cbh")
			return testDigest
		}

		Convey("Never seen before tarball", func() {
			builder.provenance = func(gs string) string {
				So(gs, ShouldEqual, testTarballURL+"#1") // used first gen
				return digest                            // got its digest correctly
			}

			res, err := runBuild(ctx, buildParams{
				Manifest:     &manifest.Manifest{Name: testTargetName},
				Image:        testImageName,
				BuildID:      "b1",
				CanonicalTag: testTagName,
				Stage:        stageFileSet(fs),
				Store:        store,
				Builder:      builder,
				Registry:     registry,
			})
			So(err, ShouldBeNil)

			// Uploaded the file.
			obj, err := store.Check(ctx, testTarballPath)
			So(err, ShouldBeNil)
			So(obj.String(), ShouldEqual, testTarballURL+"#1") // uploaded the first gen

			// Used Cloud Build.
			So(res, ShouldResemble, &buildResult{
				Image: &imageRef{
					Image:        testImageName,
					Digest:       testDigest,
					CanonicalTag: testTagName,
					BuildID:      "b1",
				},
			})

			// Tagged it.
			img, err := registry.GetImage(ctx, fmt.Sprintf("%s:%s", testImageName, testTagName))
			So(err, ShouldBeNil)
			So(img.Digest, ShouldEqual, testDigest)

			// Now we build this exact tarball again using different canonical tag.
			// We should get back the image we've already built.
			Convey("Building existing tarball reuses the image", func() {
				builder.provenance = func(gs string) string {
					panic("Cloud Build should not be invoked")
				}

				// To avoid clashing on metadata keys that depend on timestamps.
				tc.Add(time.Minute)

				res, err := runBuild(ctx, buildParams{
					Manifest:     &manifest.Manifest{Name: testTargetName},
					Image:        testImageName,
					BuildID:      "b2",
					CanonicalTag: "another-tag",
					Stage:        stageFileSet(fs),
					Store:        store,
					Builder:      builder,
					Registry:     registry,
				})
				So(err, ShouldBeNil)

				// Reused the existing image.
				So(res, ShouldResemble, &buildResult{
					Image: &imageRef{
						Image:        testImageName,
						Digest:       testDigest,
						CanonicalTag: testTagName,
						BuildID:      "b1", // was build there
					},
				})

				// Both builds are associated with the tarball via its metadata now.
				tarball, err := store.Check(ctx, testTarballPath)
				So(err, ShouldBeNil)
				md := tarball.Metadata.Values(buildRefMetaKey)
				So(md, ShouldHaveLength, 2)
				So(md[0].Value, ShouldEqual, `{"build_id":"b2","tag":"another-tag"}`)
				So(md[1].Value, ShouldEqual, `{"build_id":"b1","tag":"canonical-tag"}`)
			})
		})

		Convey("Already seen canonical tag", func() {
			registry.put(fmt.Sprintf("%s:%s", testImageName, testTagName), testDigest)

			res, err := runBuild(ctx, buildParams{
				Manifest:     &manifest.Manifest{Name: testTargetName},
				Image:        testImageName,
				CanonicalTag: testTagName,
				Registry:     registry,
			})
			So(err, ShouldBeNil)

			// Reused the existing image.
			So(res, ShouldResemble, &buildResult{
				Image: &imageRef{
					Image:        testImageName,
					Digest:       testDigest,
					CanonicalTag: testTagName,
				},
			})
		})

		Convey("No registry is set => nothing is uploaded", func() {
			builder.provenance = func(gs string) string {
				So(gs, ShouldEqual, testTarballURL+"#1") // used first gen
				return digest                            // got its digest correctly
			}

			res, err := runBuild(ctx, buildParams{
				Manifest:     &manifest.Manifest{Name: testTargetName},
				CanonicalTag: testTagName, // ignored
				Stage:        stageFileSet(fs),
				Store:        store,
				Builder:      builder,
				Registry:     registry,
			})
			So(err, ShouldBeNil)

			// Uploaded the file.
			obj, err := store.Check(ctx, testTarballPath)
			So(err, ShouldBeNil)
			So(obj.String(), ShouldEqual, testTarballURL+"#1") // uploaded the first gen

			// Did NOT produce any image.
			So(res, ShouldResemble, &buildResult{})
		})

		Convey("Cloud Build build failure", func() {
			builder.finalStatus = cloudbuild.StatusFailure
			_, err := runBuild(ctx, buildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Image:    testImageName,
				Stage:    stageFileSet(fs),
				Store:    store,
				Builder:  builder,
				Registry: registry,
			})
			So(err, ShouldErrLike, "build failed, see its logs")
		})

		Convey("Cloud Build API errors", func() {
			builder.checkCallback = func(b *runningBuild) error {
				return fmt.Errorf("boom")
			}
			_, err := runBuild(ctx, buildParams{
				Manifest: &manifest.Manifest{Name: testTargetName},
				Image:    testImageName,
				Stage:    stageFileSet(fs),
				Store:    store,
				Builder:  builder,
				Registry: registry,
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

func stageFileSet(fs *fileset.Set) stageCallback {
	return func(c context.Context, m *manifest.Manifest, cb func(*fileset.Set) error) error {
		return cb(fs)
	}
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
		Metadata:   &storage.Metadata{},
	}

	s.blobs[name] = objBlob{
		Object: obj,
		Blob:   blob,
	}
	return &obj, nil
}

func (s *storageImplMock) UpdateMetadata(ctx context.Context, obj *storage.Object, cb func(m *storage.Metadata) error) error {
	itm, ok := s.blobs[obj.Name]
	if !ok {
		return fmt.Errorf("can't update metadata of %q: no such object", obj.Name)
	}

	md := itm.Metadata.Clone()
	if err := cb(md); err != nil || itm.Metadata.Equal(md) {
		return err
	}
	itm.Metadata = md

	s.blobs[obj.Name] = itm
	return nil
}

////////////////////////////////////////////////////////////////////////////////

type builderImplMock struct {
	// Can be touched.
	checkCallback func(b *runningBuild) error
	finalStatus   cloudbuild.Status
	provenance    func(gs string) string  // gs://.... => SHA256
	outputDigests func(img string) string // full image name => "sha256:..."

	// Shouldn't be touched.
	registry *registryImplMock
	nextID   int64
	builds   map[string]runningBuild
}

type runningBuild struct {
	cloudbuild.Build
	Request cloudbuild.Request
}

func newBuilderImplMock(r *registryImplMock) *builderImplMock {
	bld := &builderImplMock{
		builds:        make(map[string]runningBuild, 0),
		finalStatus:   cloudbuild.StatusSuccess,
		provenance:    func(string) string { return "" },
		outputDigests: func(string) string { return "" },
		registry:      r,
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
	if build.Status == cloudbuild.StatusSuccess && build.Request.Image != "" {
		b.registry.put(build.Request.Image, build.OutputDigest)
	}
	return &build.Build, nil
}

////////////////////////////////////////////////////////////////////////////////

type registryImplMock struct {
	imgs map[string]registry.Image // <image>[:<tag>|@<digest>] => Image
}

func newRegistryImplMock() *registryImplMock {
	return &registryImplMock{
		imgs: make(map[string]registry.Image, 0),
	}
}

// put takes "<name>:<tag> => <digest>" image and puts it in the registry.
func (r *registryImplMock) put(image, digest string) {
	if !strings.HasPrefix(digest, "sha256:") {
		panic(digest)
	}

	var name, tag string
	switch chunks := strings.Split(image, ":"); {
	case len(chunks) == 1:
		name, tag = chunks[0], "latest"
	case len(chunks) == 2:
		name, tag = chunks[0], chunks[1]
	default:
		panic(image)
	}

	img := registry.Image{
		Registry:    "...",
		Repo:        name,
		Digest:      digest,
		RawManifest: []byte(fmt.Sprintf("raw manifest of %q", digest)),
	}

	r.imgs[fmt.Sprintf("%s@%s", name, digest)] = img
	r.imgs[fmt.Sprintf("%s:%s", name, tag)] = img
}

func (r *registryImplMock) GetImage(ctx context.Context, image string) (*registry.Image, error) {
	img, ok := r.imgs[image]
	if !ok {
		return nil, &registry.Error{
			Errors: []registry.InnerError{
				{Code: "MANIFEST_UNKNOWN"},
			},
		}
	}
	return &img, nil
}

func (r *registryImplMock) TagImage(ctx context.Context, img *registry.Image, tag string) error {
	r.imgs[fmt.Sprintf("%s:%s", img.Repo, tag)] = *img
	return nil
}
