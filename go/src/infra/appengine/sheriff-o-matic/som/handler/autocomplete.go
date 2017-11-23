package handler

import (
	"encoding/csv"
	"encoding/json"
	"index/suffixarray"
	"strings"

	"cloud.google.com/go/storage"
	"golang.org/x/net/context"
	"google.golang.org/appengine"

	"go.chromium.org/gae/service/info"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
)

const (
	bucketName      = "sheriff-o-matic.appspot.com/autocomplete"
	userCSVFileName = "chromium-users.csv"
	sentinel        = "\x00"
)

type autocompleter struct {
	data []byte
	sa   *suffixarray.Index
}

func newAutocompleter(emails []string) *autocompleter {
	data := []byte(sentinel + strings.Join(emails, sentinel) + sentinel)

	return &autocompleter{
		data: data,
		sa:   suffixarray.New(data),
	}
}

func (ac *autocompleter) query(query string) []string {
	indices := ac.sa.Lookup([]byte(query), -1)
	results := make([]string, len(indices))

	// The indices returned from the suffix array index lookup point to
	// locations in the concatenated bytes of the original input array, not to
	// locations in the original input array. This function takes the match
	// position from result and searches backwards and forwards until it hits
	// sentinal values indicating the start and end of the full match within
	// the concatenated byte array.
	stringForIndex := func(index int) string {
		start, end := 0, 0
		for i := index - 1; i >= 0; i-- {
			if ac.data[i] == 0 {
				start = i + 1
				break
			}
		}

		for i := index + 1; i < len(ac.data); i++ {
			if ac.data[i] == 0 {
				end = i
				break
			}
		}

		return string(ac.data[start:end])
	}

	for i, idx := range indices {
		results[i] = stringForIndex(idx)
	}

	return results
}

func readCSV(c context.Context) ([]string, error) {
	client, err := storage.NewClient(c)
	if err != nil {
		logging.Errorf(c, "getting storage client: %v", err)
		return nil, err
	}

	bucket := client.Bucket(bucketName)
	fileReader, err := bucket.Object(userCSVFileName).NewReader(c)
	if err != nil {
		logging.Errorf(c, "reading csv file: %v", err)
		return nil, err
	}
	csvReader := csv.NewReader(fileReader)

	rows, err := csvReader.ReadAll()
	if err != nil {
		logging.Errorf(c, "reading all csv: %v", err)
		return nil, err
	}

	emails := make([]string, len(rows))

	for i, row := range rows {
		emails[i] = row[0]
	}
	return emails, nil
}

func getAutocompleter(c context.Context) (*autocompleter, error) {
	// TODO: Cache this between requests so we're not reading from
	// GCS and constructing the suffix array index so frequently.
	emails, err := readCSV(c)
	if err != nil {
		logging.Errorf(c, "reading CSV: %v", err)
		return nil, err
	}
	ac := newAutocompleter(emails)

	return ac, nil
}

// GetUserAutocompleteHandler returns chromium developer email addresses
// that match the query string.
func GetUserAutocompleteHandler(ctx *router.Context) {
	c, w, r, p := ctx.Context, ctx.Writer, ctx.Request, ctx.Params

	aec := c
	if info.AppID(c) != "" && info.AppID(c) != "app" {
		aec = appengine.NewContext(r)
	}

	ac, err := getAutocompleter(aec)
	if err != nil {
		logging.Errorf(c, "getting autocompleter: %v", err)
		return
	}

	query := p.ByName("query")

	// TODO: sort by relevance, like position of the match in the result
	// so that earlier matches rank higer than later matches.
	results := ac.query(query)
	respData, err := json.Marshal(results)
	if err != nil {
		logging.Errorf(c, "marshaling json: %v", err)
		return
	}

	w.Write(respData)
}
