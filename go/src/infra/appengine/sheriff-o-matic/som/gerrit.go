package som

import (
	"net/http"

	"golang.org/x/net/context"

	"github.com/luci/luci-go/server/auth"

	gerrit "github.com/andygrunwald/go-gerrit"
)

func getGerritClient(c context.Context, instanceURL string) (*gerrit.Client, error) {
	tr, err := auth.GetRPCTransport(c, auth.AsSelf,
		auth.WithScopes("https://www.googleapis.com/auth/gerritcodereview"))
	if err != nil {
		return nil, err
	}

	httpc := &http.Client{Transport: tr}
	client, err := gerrit.NewClient(instanceURL, httpc)
	if err != nil {
		return nil, err
	}

	// This is a workaround to force the client lib to prepend /a to paths.
	client.Authentication.SetCookieAuth("not-used", "not-used")

	return client, nil
}

func createCL(client *gerrit.Client, project, branch, subject string, fileContents map[string]string) (string, error) {
	changeInput := &gerrit.ChangeInfo{
		Project: project,
		Branch:  branch,
		Subject: subject,
		Status:  "DRAFT",
		Topic:   "",
	}

	change, _, err := client.Changes.CreateChange(changeInput)
	if err != nil {
		return "", err
	}

	// Add the changes to the new CL. Would be nice if Gerrit API had a bulk op for this.
	for path, contents := range fileContents {
		_, err = client.Changes.ChangeFileContentInChangeEdit(change.ChangeID, path, contents)
		if err != nil {
			return "", err
		}
	}

	// Publish the changes.
	// TODO: set alertNotify to something besides NONE?
	_, err = client.Changes.PublishChangeEdit(change.ChangeID, "NONE")
	if err != nil {
		return "", err
	}

	return change.ID, nil
}
