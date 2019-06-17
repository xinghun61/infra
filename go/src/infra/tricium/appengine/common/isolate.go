// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"

	"github.com/golang/protobuf/jsonpb"
	isolateservice "go.chromium.org/luci/common/api/isolate/isolateservice/v1"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/isolated"
	"go.chromium.org/luci/common/isolatedclient"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
	"go.chromium.org/luci/server/auth"

	admin "infra/tricium/api/admin/v1"
	tricium "infra/tricium/api/v1"
)

const (
	isolateDevServerURL  = "https://isolateserver-dev.appspot.com"
	isolateProdServerURL = "https://isolateserver.appspot.com"
	isolateNamespace     = "default-gzip" // The namespace to use when isolating new inputs.
)

// IsolateAPI defines the interface to the isolate server.
//
// The interface is tuned to the needs of Tricium and Tricium data.
type IsolateAPI interface {
	// IsolateGitFileDetails isolates Git file details based on the
	// corresponding Tricium data type definition.
	//
	// The Git file details data type should be isolated with the following
	// path tricium/data/git_file_details.json and the data format as specified
	// in tricium/api/v1/data.proto.
	//
	// Note that this isolate has no command and includes no other isolates.
	IsolateGitFileDetails(c context.Context, serverURL string, d *tricium.Data_GitFileDetails) (string, error)

	// IsolateWorker isolates the provided worker.
	//
	// The provided isolated input hash is included in the worker isolate.
	// The command of the worker is used as the command of the worker isolate.
	IsolateWorker(c context.Context, serverURL string, worker *admin.Worker, isolatedInput string) (string, error)

	// LayerIsolates creates isolates files from the provided isolates
	// input and output.
	//
	// Layered isolates are used to communicate data from one worker to its
	// successor workers. The content of the isolates output is copied and
	// the provided isolated input is added as an include.
	//
	// The input and output use the same hash namespace.
	LayerIsolates(c context.Context, serverURL, namespace, isolatedInput, isolatedOutput string) (string, error)

	// FetchIsolatedResult fetches isolated Tricium result output as a JSON
	// string.
	//
	// The output is assumed to be on the form of a Tricium result and
	// located in tricium/data/results.json in the isolated output.
	FetchIsolatedResults(c context.Context, serverURL, namespace, isolatedOutput string) (string, error)
}

// IsolateServer implements the IsolateAPI interface.
var IsolateServer isolateServer

type isolateServer struct {
}

// IsolateGitFileDetails implements the IsolateAPI interface.
func (s isolateServer) IsolateGitFileDetails(c context.Context, serverURL string, d *tricium.Data_GitFileDetails) (string, error) {
	chunks := make([]*isoChunk, 2)
	mode := 0444

	// Create Git file details chunk.
	gitDetailsData, err := (&jsonpb.Marshaler{}).MarshalToString(d)
	if err != nil {
		return "", errors.Annotate(err, "failed to marshal git file details to JSON").Err()
	}
	gitDetailsSize := int64(len(gitDetailsData))
	chunks[0] = &isoChunk{
		data:  []byte(gitDetailsData),
		isIso: false,
	}
	h := isolated.GetHash(isolateNamespace)
	chunks[0].file = &isolated.File{
		Digest: isolated.HashBytes(h, chunks[0].data),
		Mode:   &mode,
		Size:   &gitDetailsSize,
	}

	// Create isolate chunk.
	iso := isolated.New(h)
	path, err := tricium.GetPathForDataType(d)
	if err != nil {
		return "", errors.Reason("failed to get data file path, data: %v", d).Err()
	}
	iso.Files[path] = *chunks[0].file
	isoData, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err, "failed to marshal git file details isolate").Err()
	}
	isoSize := int64(len(isoData))
	chunks[1] = &isoChunk{
		data:  []byte(isoData),
		isIso: true,
	}
	chunks[1].file = &isolated.File{
		Digest: isolated.HashBytes(h, chunks[1].data),
		Mode:   &mode,
		Size:   &isoSize,
	}

	// Isolate chunks.
	if err := s.isolateChunks(c, serverURL, chunks); err != nil {
		return "", errors.Annotate(err, "failed to isolate chunks").Err()
	}

	// Return isolate hash.
	return string(chunks[1].file.Digest), nil
}

// IsolateWorker implements the IsolateAPI interface.
func (s isolateServer) IsolateWorker(c context.Context, serverURL string, worker *admin.Worker, isolatedInput string) (string, error) {
	// TODO(qyearsley): Include command deadline.
	mode := 0444
	h := isolated.GetHash(isolateNamespace)
	iso := isolated.New(h)
	switch wi := worker.Impl.(type) {
	case *admin.Worker_Recipe:
		break
	case *admin.Worker_Cmd:
		iso.Command = append([]string{wi.Cmd.Exec}, wi.Cmd.Args...)
	case nil:
		return "", errors.Reason("missing Impl when isolating worker %s", worker.Name).Err()
	default:
		return "", errors.Reason("Impl.Impl has unexpected type %T", wi).Err()
	}
	iso.Includes = []isolated.HexDigest{isolated.HexDigest(isolatedInput)}
	isoData, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err, "failed to marshal worker isolate").Err()
	}
	isoSize := int64(len(isoData))
	chunk := &isoChunk{
		data:  []byte(isoData),
		isIso: true,
	}
	chunk.file = &isolated.File{
		Digest: isolated.HashBytes(h, chunk.data),
		Mode:   &mode,
		Size:   &isoSize,
	}
	if err := s.isolateChunks(c, serverURL, []*isoChunk{chunk}); err != nil {
		return "", errors.Annotate(err, "failed to isolate chunk").Err()
	}
	return string(chunk.file.Digest), nil
}

// LayerIsolates implements the IsolateAPI interface.
func (s isolateServer) LayerIsolates(c context.Context, serverURL, namespace, isolatedInput, isolatedOutput string) (string, error) {
	mode := 0444
	outIso, err := s.fetchIsolated(c, serverURL, namespace, isolatedOutput)
	if err != nil {
		return "", errors.Annotate(err, "failed to fetch output isolate").Err()
	}
	h := isolated.GetHash(namespace)
	iso := isolated.New(h)
	iso.Files = outIso.Files
	iso.Includes = []isolated.HexDigest{isolated.HexDigest(isolatedInput)}
	isoData, err := json.Marshal(iso)
	if err != nil {
		return "", errors.Annotate(err, "failed to marshal layered isolate").Err()
	}
	isoSize := int64(len(isoData))
	chunk := &isoChunk{
		data:  []byte(isoData),
		isIso: true,
	}
	chunk.file = &isolated.File{
		Digest: isolated.HashBytes(h, chunk.data),
		Mode:   &mode,
		Size:   &isoSize,
	}
	if err := s.isolateChunks(c, serverURL, []*isoChunk{chunk}); err != nil {
		return "", errors.Annotate(err, "failed to isolate chunk for layered isolate").Err()
	}
	return string(chunk.file.Digest), nil
}

// FetchIsolatedResults implements the IsolateAPI interface.
func (s isolateServer) FetchIsolatedResults(c context.Context, serverURL, namespace, digest string) (string, error) {
	outIso, err := s.fetchIsolated(c, serverURL, namespace, digest)
	if err != nil {
		return "", errors.Annotate(err, "failed to fetch output isolate").Err()
	}
	resultsFile, ok := outIso.Files["tricium/data/results.json"]
	if !ok {
		return "", errors.Reason("missing results file in isolated output, isolated output: (%s, %s)", namespace, digest).Err()
	}
	buf := &buffer{}
	if err := s.fetch(c, serverURL, namespace, string(resultsFile.Digest), buf); err != nil {
		return "", errors.Annotate(err, "failed to fetch result file").Err()
	}
	// TODO(qyearsley): Switch to io.Reader to avoid keeping the whole buffer in memory.
	return string(buf.Bytes()), nil
}

func (s isolateServer) isolateChunks(c context.Context, serverURL string, chunks []*isoChunk) error {
	// Check presence of isolated files.
	dgsts := make([]*isolateservice.HandlersEndpointsV1Digest, len(chunks))
	for i, chnk := range chunks {
		dgsts[i] = &isolateservice.HandlersEndpointsV1Digest{
			Digest:     string(chnk.file.Digest),
			Size:       *chnk.file.Size,
			IsIsolated: chnk.isIso,
		}
	}
	client, err := s.createIsolateClient(c, serverURL, isolateNamespace)
	if err != nil {
		return err
	}
	states, err := client.Contains(c, dgsts)
	if err != nil {
		return errors.Annotate(err, "failed to check isolate contains").Err()
	}
	// Push chunks not already present in parallel.
	return parallel.FanOutIn(func(ch chan<- func() error) {
		for i, st := range states {
			if st != nil {
				i, st := i, st
				ch <- func() error {
					return client.Push(c, st, isolatedclient.NewBytesSource(chunks[i].data))
				}
			}
		}
	})
}

func (s isolateServer) fetch(c context.Context, serverURL, namespace, digest string, buf *buffer) error {
	client, err := s.createIsolateClient(c, serverURL, namespace)
	if err != nil {
		return err
	}
	if err := client.Fetch(c, isolated.HexDigest(digest), buf); err != nil {
		return errors.Annotate(err, "failed to fetch").Err()
	}
	return nil
}

func (s isolateServer) fetchIsolated(c context.Context, serverURL, namespace, digest string) (*isolated.Isolated, error) {
	buf := &buffer{}
	if err := s.fetch(c, serverURL, namespace, digest, buf); err != nil {
		return nil, errors.Annotate(err, "failed to fetch isolated").Err()
	}
	iso := &isolated.Isolated{}
	json.Unmarshal(buf.Bytes(), iso)
	logging.Fields{
		"isolatedContents": string(buf.Bytes()),
		"isolated":         iso,
	}.Infof(c, "Fetched isolated.")
	return iso, nil
}

func (s isolateServer) createIsolateClient(c context.Context, serverURL, namespace string) (*isolatedclient.Client, error) {
	authTransport, err := auth.GetRPCTransport(c, auth.AsSelf)
	if err != nil {
		return nil, errors.Annotate(err, "failed to setup auth transport for isolate client").Err()
	}
	anonTransport, err := auth.GetRPCTransport(c, auth.NoAuth)
	if err != nil {
		return nil, errors.Annotate(err, "failed to setup anonymous transport for isolate client").Err()
	}
	return isolatedclient.New(&http.Client{Transport: anonTransport}, &http.Client{Transport: authTransport},
		serverURL, namespace, nil, nil), nil
}

type isoChunk struct {
	data  []byte
	isIso bool
	file  *isolated.File
}

type buffer struct {
	bytes.Buffer
}

func (f *buffer) Seek(a int64, b int) (int64, error) {
	if a != 0 || b != 0 {
		return 0, errors.Reason("non-zero value given to buffer.Seek").Err()
	}
	f.Reset()
	return 0, nil
}

// MockIsolator mocks the IsolateAPI interface for testing.
var MockIsolator mockIsolator

type mockIsolator struct{}

// IsolateGitFileDetails is a mock function for MockIsolator.
//
// For any testing actually using the return values, create a new mock.
func (mockIsolator) IsolateGitFileDetails(c context.Context, serverURL string, d *tricium.Data_GitFileDetails) (string, error) {
	return "mockmockmock", nil
}

// IsolateWorker is a mock function for MockIsolator.
//
// For any testing actually using the return values, create a new mock.
func (mockIsolator) IsolateWorker(c context.Context, serverURL string, worker *admin.Worker, inputIsolate string) (string, error) {
	return "mockmockmock", nil
}

// LayerIsolates is a mock function for MockIsolator.
//
// For any testing that actually uses the return values, create a new mock.
func (mockIsolator) LayerIsolates(c context.Context, serverURL, namespace, isolatedInput, isolatedOutput string) (string, error) {
	return "mockmockmock", nil
}

// FetchIsolatedResults is a mock function for MockIsolator.
//
// For any testing using the return value, create a new mock.
func (mockIsolator) FetchIsolatedResults(c context.Context, serverURL, namespace, isolatedOutput string) (string, error) {
	return "mockmockmock", nil
}
