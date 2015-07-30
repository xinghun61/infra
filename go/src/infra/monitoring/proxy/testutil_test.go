// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"net/http"
)

type httpError struct {
	error
	status int
}

func badRequest(err error) *httpError {
	return &httpError{err, http.StatusBadRequest}
}

func noContent(err error) *httpError {
	return &httpError{err, http.StatusNoContent}
}

func internalServerError(err error) *httpError {
	return &httpError{err, http.StatusInternalServerError}
}

func (e *httpError) Error() string {
	if e.error == nil {
		return ""
	}
	return e.error.Error()
}

func (e *httpError) writeError(w http.ResponseWriter) {
	http.Error(w, e.Error(), e.status)
}

func (e *httpError) ok() bool {
	return http.StatusOK <= e.status && e.status < http.StatusMultipleChoices
}
