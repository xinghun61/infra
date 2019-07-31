// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dockerfile

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// Resolver knows how to resolve (image, tag) pairs into an image digest.
type Resolver interface {
	// ResolveTag resolves a single image tag into a digest.
	//
	// 'image' and 'tag' here come from "FROM <image>[:<tag>]" line in
	// the Dockerfile verbatim, except 'tag' is set to "latest" if using the brief
	// "FROM <image>" form and 'image' is never "scratch" ("FROM scratch" lines
	// are treated as magical).
	//
	// The result is expected to be "sha256:<hex>". The "FROM" line will be
	// transformed into "FROM <image>@<digest> ...".
	ResolveTag(image, tag string) (digest string, err error)
}

// Resolve returns a copy of the Dockerfile with image tags resolved to
// concrete digests.
//
// Understands only the following constructs currently:
//  * FROM <image> [AS <name>] (assumes "latest" tag)
//  * FROM <image>[:<tag>] [AS <name>] (resolves the given tag)
//  * FROM <image>[@<digest>] [AS <name>] (passes the definition through)
//
// In particular does not understand ARGs, e.g. "FROM base:${CODE_VERSION}" is
// not supported. Returns an error with unrecognized line in this case.
//
// Returns the body of the resolved docker file.
func Resolve(in []byte, resolver Resolver) (out []byte, err error) {
	r := bufio.NewReader(bytes.NewReader(in))
	w := bytes.Buffer{}

	eof, lineno := false, 0
	for !eof {
		line, err := r.ReadString('\n')
		if err != nil && err != io.EOF {
			// This should not be possible, we are reading from memory.
			panic(errors.Annotate(err, "unexpected IO error").Err())
		}

		lineno++
		eof = err == io.EOF

		terms := strings.Fields(line)
		if len(terms) >= 1 && strings.ToLower(terms[0]) == "from" {
			if err := resolveFromLine(terms, resolver); err != nil {
				return nil, errors.Annotate(err, "line %d", lineno).Err()
			}
			newLine := strings.Join(terms, " ")
			if strings.HasSuffix(line, "\n") {
				line = newLine + "\n"
			} else {
				line = newLine
			}
		}

		w.WriteString(line)
	}

	return w.Bytes(), nil
}

// resolveFromLine mutates 'terms' in place by resolving image tags there.
//
// 'terms' is ["FROM", "<image>", ...].
func resolveFromLine(terms []string, r Resolver) error {
	if len(terms) < 2 {
		return errors.Reason("expecting 'FROM <image>', got only FROM").Err()
	}

	// In happy case this is one of:
	//   * <image>
	//   * <image>:<tag>
	//   * <image>@<digest>
	//
	// In unhappy case this is some nonsense and we assume Resolver is capable of
	// rejecting it.
	var img, tag string
	switch imgRef := terms[1]; {
	case strings.ContainsRune(imgRef, '$'):
		return errors.Reason("bad FROM reference %q, ARGs in FROM are not supported by cloudbuildhelper", imgRef).Err()
	case strings.ContainsRune(imgRef, '@'):
		return nil // already using a digest, no need to resolve anything
	case strings.ContainsRune(imgRef, ':'):
		chunks := strings.SplitN(imgRef, ":", 2)
		img, tag = chunks[0], chunks[1]
	default:
		img, tag = imgRef, "latest"
	}

	// "FROM scratch" is a magical line, it's not really a reference to an image,
	// at least not in a modern Docker.
	if img == "scratch" {
		terms[1] = "scratch"
		return nil
	}

	digest, err := r.ResolveTag(img, tag)
	if err != nil {
		return errors.Annotate(err, "resolving %q", img+":"+tag).Err()
	}

	terms[1] = fmt.Sprintf("%s@%s", img, digest)
	return nil
}
