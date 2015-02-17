// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package logstore

import "net/http"

// Fetch fetches file from path in logstore.
func Fetch(client *http.Client, path string) (*http.Response, error) {
	fileURL, err := URL(path)
	if err != nil {
		return nil, err
	}
	fileReq, err := http.NewRequest("GET", fileURL.String(), nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(fileReq)
	if err != nil {
		return nil, err
	}
	for _, h := range hopHeaders {
		resp.Header.Del(h)
	}
	return resp, nil
}

var hopHeaders = []string{
	"Connection",
	"Keep-Alive",
	"Proxy-Authenticate",
	"Proxy-Authorization",
	"Te",
	"Trailers",
	"Transfer-Encoding",
	"Upgrade",
}
