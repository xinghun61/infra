package client

import (
	"bytes"
	"encoding/json"
	"infra/monitoring/messages"
	"strings"

	"go.chromium.org/luci/common/logging"
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

// FinditBuildbucket fetches items from the findit service using buildbucket concept, which identifies possible culprit CLs for a failed build.
func (f *findit) FinditBuildbucket(ctx context.Context, buildID int64, failedSteps []string) ([]*messages.FinditResultV2, error) {
	data := map[string]interface{}{
		"requests": []map[string]interface{}{
			{
				"build_id":     buildID,
				"failed_steps": failedSteps,
			},
		},
	}

	b := bytes.NewBuffer(nil)
	err := json.NewEncoder(b).Encode(data)

	if err != nil {
		return nil, err
	}

	URL := f.Host + "/_ah/api/findit/v1/lucibuildfailure"
	res := &FinditAPIResponseV2{}
	if code, err := f.postJSON(ctx, URL, b.Bytes(), res); err != nil {
		logging.Errorf(ctx, "Error (%d) fetching %s: %v", code, URL, err)
		return nil, err
	}

	return res.Responses, nil
}

// NewFindit registers a findit client pointed at host.
func NewFindit(host string) FindIt {
	return &findit{simpleClient{Host: host, Client: nil}}
}
