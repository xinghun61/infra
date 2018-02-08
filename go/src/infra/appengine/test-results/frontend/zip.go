package frontend

import (
	"archive/zip"
	"bytes"
	"fmt"
	"io/ioutil"
	"net/http"
	"strings"

	"golang.org/x/net/context"

	"go.chromium.org/luci/common/gcloud/gs"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
)

// getZipHandler handles a request to get a file from a zip archive.
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

	contents, err := getZipFile(c, builder, buildNum, filepath)
	if err != nil {
		panic(err)
	}

	if contents == nil {
		contentPath := strings.Join(strings.Split(r.URL.Path, "/")[3:], "/")
		w.WriteHeader(404)
		w.Write([]byte(fmt.Sprintf("%s not found", contentPath)))
		return
	}

	// The order of these statements matters. See net/http docs for more info.
	w.Header().Set("Content-Type", http.DetectContentType(contents))
	w.WriteHeader(200)
	w.Write(contents)
}

const megabyte = 1 << 20
const chunkSize = megabyte * 31

// getZipFile retrieves a file from a layout test archive for a build number from a builder.
func getZipFile(c context.Context, builder, buildNum, filepath string) ([]byte, error) {
	gsPath := gs.Path(fmt.Sprintf("gs://chromium-layout-test-archives/%s/%s/layout-test-results.zip", builder, buildNum))
	logging.Debugf(c, "Getting google storage path %s", gsPath)

	transport, err := auth.GetRPCTransport(c, auth.NoAuth)
	if err != nil {
		return nil, err
	}

	cl, err := gs.NewProdClient(c, transport)
	if err != nil {
		return nil, err
	}

	var offset int64
	allBytes := []byte{}
	for {
		logging.Debugf(c, "reading cloud storage with offset %d", offset)
		cloudReader, err := cl.NewReader(gsPath, offset, chunkSize)
		if err != nil {
			return nil, err
		}

		readBytes, err := ioutil.ReadAll(cloudReader)
		if err != nil {
			return nil, err
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
		return nil, err
	}

	for _, f := range zr.File {
		if f.Name == filepath {
			freader, err := f.Open()
			if err != nil {
				return nil, err
			}

			return ioutil.ReadAll(freader)
		}
	}

	return nil, nil
}
