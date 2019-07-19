// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package registry implements very limited Container Registry v2 API client.
//
// It is not universal and primarily targets Google Container Registry
// implementation. In particular it uses Google OAuth2 tokens for
// authentication.
package registry

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"strings"
	"sync"

	"golang.org/x/oauth2"

	"go.chromium.org/luci/common/errors"
)

var (
	// ErrUnrecognizedRegistry is returned when the registry hostname is unknown to us.
	ErrUnrecognizedRegistry = errors.New("unrecognized registry")
	// ErrBadRegistryResponse is returned if the registry returns unexpected response.
	ErrBadRegistryResponse = errors.New("unrecognized or wrong response from the registry")
)

// See https://github.com/docker/distribution/blob/master/docs/spec/manifest-v2-2.md#media-types.
var manifestMediaTypes = []string{
	"application/vnd.docker.distribution.manifest.v1+json",
	"application/vnd.docker.distribution.manifest.v2+json",
	"application/vnd.docker.distribution.manifest.list.v2+json",
}

// knownManifestMediaType is true if mt is in manifestMediaTypes.
func knownManifestMediaType(mt string) bool {
	for _, known := range manifestMediaTypes {
		if mt == known {
			return true
		}
	}
	return false
}

// Client is very limited Container Registry v2 API client.
//
// It can resolve <image>:<tag> into <image>@sha256@... and can tag already
// uploaded images.
type Client struct {
	TokenSource oauth2.TokenSource // tokens to use for gcr.io auth

	m    sync.Mutex
	auth map[string]*authService // registry hostname => auth service for it
}

// Image points to some concreter docker image manifest.
type Image struct {
	Registry    string // the hostname of a registry the image came from
	Repo        string // the name of the repo with the image
	Digest      string // the manifest digest as "sha256:<hex>" string
	MediaType   string // MIME type of the manifest stored there
	RawManifest []byte // the raw manifest body (format depends on the media type)
}

// Reference returns identifier of this image as it may appear in Dockerfile.
func (i *Image) Reference() string {
	return fmt.Sprintf("%s/%s@%s", i.Registry, i.Repo, i.Digest)
}

// GetImage takes an image reference as it appears in Dockerfile and returns
// an image manifest, including its sha256 digest.
//
// The image reference has the same format as in Dockerfile.
func (c *Client) GetImage(ctx context.Context, image string) (*Image, error) {
	// gcr.io/project/image:tag => (gcr.io, project/image, tag).
	registry, repo, ref, err := splitImageName(image)
	if err != nil {
		return nil, errors.Annotate(err, "bad image reference %q", image).Err()
	}

	req, _ := http.NewRequest("GET", manifestURL(registry, repo, ref), nil)

	// Note that "Accept" header with the explicit enumeration of recognized media
	// types is required and if the request image is using some newer manifest
	// format we don't understand, this request will fail.
	req.Header.Set("Accept", strings.Join(manifestMediaTypes, ", "))

	// Attach Authorization header, if the registry needs it.
	if err := c.authorizeRequest(ctx, req, registry, repo, "pull"); err != nil {
		return nil, errors.Annotate(err, "failed to authorize the pull request").Err()
	}

	resp, body, err := sendJSONRequest(ctx, req, nil)
	if err != nil {
		return nil, errors.Annotate(err, "failed to grab the image manifest").Err()
	}

	// The media type is required and should be one of the requested ones.
	mt := resp.Header.Get("Content-Type")
	if !knownManifestMediaType(mt) {
		return nil, errors.Annotate(ErrBadRegistryResponse, "unexpected media type %q", mt).Err()
	}

	// The manifest body digest is what we are after. It uniquely identifies
	// the image and can be used to pull the image from the registry.
	digest := strings.ToLower(resp.Header.Get("Docker-Content-Digest"))
	switch {
	case digest == "":
		return nil, errors.Annotate(ErrBadRegistryResponse, "no Docker-Content-Digest header").Err()
	case !strings.HasPrefix(digest, "sha256:"):
		return nil, errors.Annotate(ErrBadRegistryResponse, "unrecognized digest algo in %q, we support only sha256", digest).Err()
	}

	// docker.io is broken for non-list manifests, returning wrong hash for them.
	// See https://github.com/docker/distribution/issues/2395. So do the digest
	// check only when seeing list.v2 manifests or *not* using docker.io.
	if registry != "docker.io" || mt == "application/vnd.docker.distribution.manifest.list.v2+json" {
		h := sha256.Sum256(body)
		dgst := "sha256:" + hex.EncodeToString(h[:])
		if digest != dgst {
			return nil, errors.Annotate(ErrBadRegistryResponse, "expected a manifest with digest %q, but got %q", digest, dgst).Err()
		}
	}

	return &Image{
		Registry:    registry,
		Repo:        repo,
		Digest:      digest,
		MediaType:   mt,
		RawManifest: body,
	}, nil
}

// TagImage sets a tag on the given already uploaded image.
//
// Tagging an image is just pushing its manifest under a new name.
func (c *Client) TagImage(ctx context.Context, img *Image, tag string) error {
	req, err := http.NewRequest("PUT", manifestURL(img.Registry, img.Repo, tag), bytes.NewReader(img.RawManifest))
	if err != nil {
		return errors.Annotate(err, "failed to create HTTP request").Err()
	}
	req.Header.Set("Content-Type", img.MediaType)
	if err := c.authorizeRequest(ctx, req, img.Registry, img.Repo, "push"); err != nil {
		return errors.Annotate(err, "failed to authorize the push request").Err()
	}
	_, _, err = sendJSONRequest(ctx, req, nil)
	return errors.Annotate(err, "failed to attach a tag").Err()
}

// authorizeRequest appends an authorization header to the request.
func (c *Client) authorizeRequest(ctx context.Context, req *http.Request, registry, repo, scopes string) error {
	switch auth, err := c.authServiceFor(ctx, registry); {
	case err != nil:
		return errors.Annotate(err, "no authorization service").Err()
	case auth != nil:
		if err := auth.authorizeRequest(ctx, req, repo, scopes); err != nil {
			return errors.Annotate(err, "failed to get docker registry auth token").Err()
		}
	}
	return nil
}

// authServiceFor returns an authorization service to use for given registry.
func (c *Client) authServiceFor(ctx context.Context, registry string) (*authService, error) {
	c.m.Lock()
	defer c.m.Unlock()

	if auth := c.auth[registry]; auth != nil {
		return auth, nil
	}

	// To see what auth service a registry is using, send it unauthenticated
	// request and look at Www-authenticate header, e.g.
	//
	// $ curl -v https://gcr.io/v2/ 2>&1 | grep www-authenticate
	// < www-authenticate: Bearer realm="https://gcr.io/v2/token",service="gcr.io"
	//
	// TODO(vadimsh): Discover the auth service location dynamically. We currently
	// assume names of existing auth services won't change, but this is not really
	// guaranteed by the protocol or individual registries.
	var auth *authService
	switch {
	case registry == "docker.io":
		auth = &authService{
			realm:   "https://auth.docker.io/token",
			service: "registry.docker.io", // yep, not registry-1.docker.io, not docker.io
		}
	case registry == "gcr.io" || strings.HasSuffix(registry, ".gcr.io"):
		auth = &authService{
			realm:   fmt.Sprintf("https://%s/v2/token", registry),
			service: registry,
			ts:      c.TokenSource,
		}
	case registry == "mcr.microsoft.com":
		auth = nil // anonymous access
	default:
		return nil, errors.Annotate(ErrUnrecognizedRegistry, "unknown registry %q", registry).Err()
	}

	if c.auth == nil {
		c.auth = make(map[string]*authService, 1)
	}
	c.auth[registry] = auth
	return auth, nil
}

// splitImageName parses image name into its components.
//
// Takes "<registry>/<repo>(:|@)<ref>" and returns each individual component.
func splitImageName(image string) (registry, repo, ref string, err error) {
	var chunks []string
	switch {
	case strings.ContainsRune(image, '@'):
		chunks = strings.SplitN(image, "@", 2)
	case strings.ContainsRune(image, ':'):
		chunks = strings.SplitN(image, ":", 2)
	default:
		chunks = []string{image, "latest"} // "latest" is default tag in Docker
	}

	img := chunks[0]
	ref = chunks[1]

	// See https://github.com/docker/distribution/blob/master/reference/normalize.go
	// for defaults.
	switch strings.Count(img, "/") {
	case 0: // e.g. "ubuntu"
		registry = "docker.io"
		repo = "library/" + img
	case 1: // e.g. "library/ubuntu"
		registry = "docker.io"
		repo = img
	default: // e.g. "gcr.io/something/something"
		registry = img[:strings.IndexRune(img, '/')]
		repo = img[len(registry)+1:]
	}
	return
}

// manifestURL constructs URL to a manifest in v2 registry.
func manifestURL(registry, repo, ref string) string {
	// It appears the default docker.io registry is supposed to resolve into
	// registry-1.docker.io somehow. This mechanism appears to be undocumented,
	// probably due to some legacy reason.
	registryHost := registry
	if registry == "docker.io" {
		registryHost = "registry-1.docker.io"
	}
	return fmt.Sprintf("https://%s/v2/%s/manifests/%s", registryHost, repo, ref)
}
