package frontend

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"golang.org/x/net/context"

	"cloud.google.com/go/storage"
	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/gcloud/gs"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

// getZipHandler handles a request to get a file from a zip archive.
// This saves content etags in memcache, to save round trip time on fetching
// zip files over the network, so that clients can cache the data.
func getZipHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	builder := p.ByName("builder")
	buildNum := p.ByName("buildnum")
	filepath := strings.Trim(p.ByName("filepath"), "/")

	// Special case, since this isn't the zip file.
	if filepath == "layout-test-results.zip" {
		newURL := fmt.Sprintf("https://storage.googleapis.com/chromium-layout-test-archives/%s/%s/%s", builder, buildNum, filepath)
		http.Redirect(w, r, newURL, http.StatusPermanentRedirect)
		return
	}
	mkey := fmt.Sprintf("gs_etag%s/%s/%s", builder, buildNum, filepath)

	// This content should never change; safe to cache for 1 day.
	w.Header().Set("Cache-Control", "public, max-age=86400")

	// Check to see if the client has this cached on their side.
	ifNoneMatch := r.Header.Get("If-None-Match")
	itm := memcache.NewItem(c, mkey)
	if ifNoneMatch != "" {
		err := memcache.Get(c, itm)
		if err == nil && r.Header.Get("If-None-Match") == string(itm.Value()) {
			w.WriteHeader(http.StatusNotModified)
			return
		}
	}

	contents, err := getZipFile(c, builder, buildNum, filepath)
	if err != nil {
		panic(err)
	}

	if contents == nil {
		w.WriteHeader(http.StatusNotFound)
		w.Write([]byte("not found"))
		return
	}

	h := sha256.New()
	h.Write(contents)
	itm.SetValue([]byte(fmt.Sprintf("%x", h.Sum(nil))))
	err = memcache.Set(c, itm)
	if err != nil {
		logging.Warningf(c, "Error while setting memcache key for etag digest: %v", err)
	} else {
		w.Header().Set("ETag", string(itm.Value()))
	}

	// The order of these statements matters. See net/http docs for more info.
	w.Header().Set("Content-Type", http.DetectContentType(contents))
	w.WriteHeader(http.StatusOK)
	w.Write(contents)
}

const megabyte = 1 << 20
const chunkSize = megabyte * 31

// knownPrefixes is a list of strings that we know will exist in the google storage bucket.
// If the first path element in the filepath is not on this list, it's assumed to be a substep,
// and the zip file in that subdirectory is used, instead of at the root of the build number bucket.
var knownPrefixes = []string{
	"layout-test-results",
	"retry_summary.json",
}

// getZipFile retrieves a file from a layout test archive for a build number from a builder.
var getZipFile = func(c context.Context, builder, buildNum, filepath string) ([]byte, error) {
	prefix := ""
	found := false
	for _, prefix := range knownPrefixes {
		if strings.HasPrefix(filepath, prefix) {
			found = true
		}
	}

	if !found && strings.Contains(filepath, "/") {
		prefix = strings.Split(filepath, "/")[0] + "/"
		filepath = strings.Join(strings.Split(filepath, "/")[1:], "/")
	}
	gsPath := gs.Path(fmt.Sprintf("gs://chromium-layout-test-archives/%s/%s/%slayout-test-results.zip", builder, buildNum, prefix))
	logging.Debugf(c, "Getting google storage path %s", gsPath)

	transport, err := auth.GetRPCTransport(c, auth.NoAuth)
	if err != nil {
		return nil, fmt.Errorf("while creating transport: %v", err)
	}

	cl, err := gs.NewProdClient(c, transport)
	if err != nil {
		return nil, fmt.Errorf("while creating client: %v", err)
	}

	var offset int64
	allBytes := []byte{}
	for {
		cloudReader, err := cl.NewReader(gsPath, offset, chunkSize)
		if err != nil && err != storage.ErrObjectNotExist {
			return nil, fmt.Errorf("while creating reader: %v", err)
		}
		if err == storage.ErrObjectNotExist {
			return nil, nil
		}

		readBytes, err := ioutil.ReadAll(cloudReader)
		if err != nil {
			return nil, fmt.Errorf("while reading bytes: %v", err)
		}

		allBytes = append(allBytes, readBytes...)
		offset += int64(len(readBytes))
		if len(readBytes) < chunkSize {
			break
		}
	}

	bytesReader := bytes.NewReader(allBytes)
	zr, err := zip.NewReader(bytesReader, int64(len(allBytes)))
	if err != nil {
		return nil, fmt.Errorf("while creating zip reader: %v", err)
	}

	for _, f := range zr.File {
		if f.Name == filepath {
			freader, err := f.Open()
			if err != nil {
				return nil, fmt.Errorf("while opening zip file: %v", err)
			}

			return ioutil.ReadAll(freader)
		}
	}

	return nil, nil
}
