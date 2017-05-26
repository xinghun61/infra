// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package som implements HTTP server that handles requests to default module.
package som

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"golang.org/x/net/context"

	"github.com/luci/gae/service/datastore"
	"github.com/luci/gae/service/info"
	"github.com/luci/luci-go/appengine/gaeauth/server/gaesigner"
	"github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/server/router"
)

// GetTreesHandler returns a JSON list of all the trees SoM knows about.
func GetTreesHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	q := datastore.NewQuery("Tree")
	results := []*Tree{}
	err := datastore.GetAll(c, q, &results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	txt, err := json.Marshal(results)
	if err != nil {
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(txt)
}

// GetTreeLogoHandler returns a signed URL to an image asset hosted on GCS.
func GetTreeLogoHandler(ctx *router.Context) {
	c, w := ctx.Context, ctx.Writer

	sa, err := info.ServiceAccount(c)
	if err != nil {
		logging.Errorf(c, "failed to get service account: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}

	getTreeLogo(ctx, sa, gaesigner.Signer{})
}

type signer interface {
	SignBytes(c context.Context, b []byte) (string, []byte, error)
}

func getTreeLogo(ctx *router.Context, sa string, sign signer) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params
	tree := p.ByName("tree")
	resource := fmt.Sprintf("/%s.appspot.com/logos/%s.png", info.AppID(c), tree)
	expStr := fmt.Sprintf("%d", time.Now().Add(10*time.Minute).Unix())
	sl := []string{
		"GET",
		"", // Optional MD5, which we don't have.
		"", // Content type, ommitted because it breaks the signature.
		expStr,
		resource,
	}
	unsigned := strings.Join(sl, "\n")
	_, b, err := sign.SignBytes(c, []byte(unsigned))
	if err != nil {
		logging.Errorf(c, "failed to sign bytes: %v", err)
		errStatus(c, w, http.StatusInternalServerError, err.Error())
		return
	}
	sig := base64.StdEncoding.EncodeToString(b)
	params := url.Values{
		"GoogleAccessId": {sa},
		"Expires":        {expStr},
		"Signature":      {sig},
	}

	signedURL := fmt.Sprintf("https://storage.googleapis.com%s?%s", resource, params.Encode())
	http.Redirect(w, r, signedURL, http.StatusFound)
}
