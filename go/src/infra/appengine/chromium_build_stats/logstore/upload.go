// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logstore

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"io/ioutil"
	"net/http"
	"path"
)

// Upload uploads data to logstore and returns logPath.
// data will be compressed.
func Upload(client *http.Client, prefix string, data []byte) (string, error) {
	hd := sha256.Sum256(data)
	h := base64.URLEncoding.EncodeToString(hd[:])
	logPath := path.Join("upload", fmt.Sprintf("%s.%s.gz", prefix, h))
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	gw.Write(data)
	err := gw.Close()
	if err != nil {
		return "", err
	}

	// https://cloud.google.com/storage/docs/json_api/v1/how-tos/upload#simple
	requrl := fmt.Sprintf(`https://www.googleapis.com/upload/storage/v1/b/chromium-build-stats.appspot.com/o?uploadType=media&name=%s`, logPath)
	resp, err := client.Post(requrl, "application/octet-data", bytes.NewReader(buf.Bytes()))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, err := ioutil.ReadAll(resp.Body)
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("upload status: %s %d %s: %s: %v", requrl, resp.StatusCode, resp.Status, body, err)
	}
	return logPath, nil
}
