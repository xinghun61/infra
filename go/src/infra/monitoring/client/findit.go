package client

import (
	"bytes"
	"encoding/json"
	"infra/monitoring/messages"
	"strings"

	"github.com/luci/luci-go/common/logging"
	"golang.org/x/net/context"
)

type findit struct {
	simpleClient
}

// Findit fetches items from the findit service, which identifies possible culprit CLs for a failed build.
func (f *findit) Findit(ctx context.Context, master *messages.MasterLocation, builder string, buildNum int64, failedSteps []string) ([]*messages.FinditResult, error) {
	// TODO(martiniss): Remove once perf is supported by findit
	if strings.Contains(master.Name(), "perf") {
		return []*messages.FinditResult{}, nil
	}

	data := map[string]interface{}{
		"builds": []map[string]interface{}{
			{
				"master_url":   master.String(),
				"builder_name": builder,
				"build_number": buildNum,
				"failed_steps": failedSteps,
			},
		},
	}

	b := bytes.NewBuffer(nil)
	err := json.NewEncoder(b).Encode(data)

	if err != nil {
		return nil, err
	}

	URL := f.Host + "/_ah/api/findit/v1/buildfailure"
	res := &FinditAPIResponse{}
	if code, err := f.postJSON(ctx, URL, b.Bytes(), res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Results, nil
}

// WithFindit registers a findit client pointed at host.
func WithFindit(ctx context.Context, host string) context.Context {
	f := &findit{simpleClient{Host: host, Client: nil}}
	return context.WithValue(ctx, finditKey, f)
}

// GetFindit returns the currently registered Findit client, or panics.
func GetFindit(ctx context.Context) *findit {
	ret, ok := ctx.Value(finditKey).(*findit)
	if !ok {
		panic("No findit client set in context")
	}
	return ret
}
