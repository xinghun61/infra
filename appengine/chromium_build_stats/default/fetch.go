// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package chromiumbuildstats

// fetch.go fetches log files from gs://chrome-goma-log.

import (
	"fmt"
	"net/http"
	"strings"
)

// fetch fetches path from gs://chrome-goma-log/path.
func fetch(client *http.Client, path string) (*http.Response, error) {
	if path[0] == '/' {
		path = path[1:]
	}
	fileURL := fmt.Sprintf("https://chrome-goma-log.storage.googleapis.com/%s", path)
	fileReq, err := http.NewRequest("GET", fileURL, nil)
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

func copyHeader(dst, src http.Header) {
	for k, vv := range src {
		if strings.HasPrefix(k, "X-") {
			continue
		}
		for _, v := range vv {
			dst.Add(k, v)
		}
	}
}
