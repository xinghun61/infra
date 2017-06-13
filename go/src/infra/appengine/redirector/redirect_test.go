// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"net/http/httptest"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
)

func TestRedirects(t *testing.T) {
	tests := []struct {
		URL             string
		WantRedirectURL string
		WantStatus      int
	}{
		{"https://crbug.com/", "https://bugs.chromium.org/p/chromium/", 302},
		{"https://crbug.com/new", "https://chromiumbugs.appspot.com/", 302},
		{"https://crbug.com/new/", "https://chromiumbugs.appspot.com/", 302},
		{"https://crbug.com/new/blah", "https://chromiumbugs.appspot.com/", 302},
		{"https://crbug.com/new/blah/", "https://chromiumbugs.appspot.com/", 302},
		{"https://crbug.com/new-detailed", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://crbug.com/new-detailed/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://crbug.com/new-detailed/blah", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://crbug.com/new-detailed/blah/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://crbug.com/wizard", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://crbug.com/wizard/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://crbug.com/wizard/blah", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://crbug.com/wizard/blah/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://crbug.com/1234", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://crbug.com/1234/", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://crbug.com/1234/blah", "", 404},
		{"https://crbug.com/1234/blah/", "", 404},
		{"https://crbug.com/foo", "https://bugs.chromium.org/p/foo", 302},
		{"https://crbug.com/foo/", "https://bugs.chromium.org/p/foo", 302},
		{"https://crbug.com/foo/new", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://crbug.com/foo/new/", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://crbug.com/foo/blah", "", 404},
		{"https://crbug.com/foo/blah/", "", 404},
		{"https://crbug.com/foo/1234", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://crbug.com/foo/1234/", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://crbug.com/foo/1234/blah", "", 404},
		{"https://crbug.com/foo/1234/blah/", "", 404},
		{"https://crbug.com/_foo", "", 404},
		{"https://crbug.com/foo_", "", 404},
		{"https://crbug.com/~bar", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://crbug.com/~bar/", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://crbug.com/foo/~bar", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},
		{"https://crbug.com/foo/~bar/", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},

		{"https://www.crbug.com/", "https://bugs.chromium.org/p/chromium/", 302},
		{"https://www.crbug.com/new", "https://chromiumbugs.appspot.com/", 302},
		{"https://www.crbug.com/new/", "https://chromiumbugs.appspot.com/", 302},
		{"https://www.crbug.com/new/blah", "https://chromiumbugs.appspot.com/", 302},
		{"https://www.crbug.com/new/blah/", "https://chromiumbugs.appspot.com/", 302},
		{"https://www.crbug.com/new-detailed", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://www.crbug.com/new-detailed/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://www.crbug.com/new-detailed/blah", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://www.crbug.com/new-detailed/blah/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://www.crbug.com/wizard", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://www.crbug.com/wizard/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://www.crbug.com/wizard/blah", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://www.crbug.com/wizard/blah/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://www.crbug.com/1234", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://www.crbug.com/1234/", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://www.crbug.com/1234/blah", "", 404},
		{"https://www.crbug.com/1234/blah/", "", 404},
		{"https://www.crbug.com/foo", "https://bugs.chromium.org/p/foo", 302},
		{"https://www.crbug.com/foo/", "https://bugs.chromium.org/p/foo", 302},
		{"https://www.crbug.com/foo/new", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://www.crbug.com/foo/new/", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://www.crbug.com/foo/blah", "", 404},
		{"https://www.crbug.com/foo/blah/", "", 404},
		{"https://www.crbug.com/foo/1234", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://www.crbug.com/foo/1234/", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://www.crbug.com/foo/1234/blah", "", 404},
		{"https://www.crbug.com/foo/1234/blah/", "", 404},
		{"https://www.crbug.com/_foo", "", 404},
		{"https://www.crbug.com/foo_", "", 404},
		{"https://www.crbug.com/~bar", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://www.crbug.com/~bar/", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://www.crbug.com/foo/~bar", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},
		{"https://www.crbug.com/foo/~bar/", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},

		{"https://new.crbug.com/", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/new", "https://chromiumbugs.appspot.com/", 302},
		{"https://new.crbug.com/new/", "https://chromiumbugs.appspot.com/", 302},
		{"https://new.crbug.com/new/blah", "https://chromiumbugs.appspot.com/", 302},
		{"https://new.crbug.com/new/blah/", "https://chromiumbugs.appspot.com/", 302},
		{"https://new.crbug.com/new-detailed", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://new.crbug.com/new-detailed/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://new.crbug.com/new-detailed/blah", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://new.crbug.com/new-detailed/blah/", "https://bugs.chromium.org/p/chromium/issues/entry", 302},
		{"https://new.crbug.com/wizard", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://new.crbug.com/wizard/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://new.crbug.com/wizard/blah", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://new.crbug.com/wizard/blah/", "https://www.google.com/accounts/ServiceLogin?service=ah&passive=true&continue=https://appengine.google.com/_ah/conflogin%3fcontinue=https://bugs.chromium.org/p/chromium/issues/entryafterlogin&ltmpl=", 302},
		{"https://new.crbug.com/1234", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://new.crbug.com/1234/", "https://bugs.chromium.org/p/chromium/issues/detail?id=1234", 302},
		{"https://new.crbug.com/1234/blah", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/1234/blah/", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/foo", "https://bugs.chromium.org/p/foo", 302},
		{"https://new.crbug.com/foo/", "https://bugs.chromium.org/p/foo", 302},
		{"https://new.crbug.com/foo/new", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://new.crbug.com/foo/new/", "https://bugs.chromium.org/p/foo/issues/entry", 302},
		{"https://new.crbug.com/foo/blah", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/foo/blah/", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/foo/1234", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://new.crbug.com/foo/1234/", "https://bugs.chromium.org/p/foo/issues/detail?id=1234", 302},
		{"https://new.crbug.com/foo/1234/blah", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/foo/1234/blah/", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/_foo", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/foo_", "https://chromiumbugs.appspot.com", 301},
		{"https://new.crbug.com/~bar", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://new.crbug.com/~bar/", "https://bugs.chromium.org/p/chromium/issues/list?q=owner:bar", 302},
		{"https://new.crbug.com/foo/~bar", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},
		{"https://new.crbug.com/foo/~bar/", "https://bugs.chromium.org/p/foo/issues/list?q=owner:bar", 302},
	}

	router := createRouter()
	for i, test := range tests {
		Convey(fmt.Sprintf("%d. %s", i, test.URL), t, func() {
			rr := httptest.NewRecorder()
			req := httptest.NewRequest("GET", test.URL, nil)
			router.ServeHTTP(rr, req)

			So(rr.HeaderMap.Get("Location"), ShouldEqual, test.WantRedirectURL)
			So(rr.Code, ShouldEqual, test.WantStatus)
		})
	}
}
