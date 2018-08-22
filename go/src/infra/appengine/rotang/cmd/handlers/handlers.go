package handlers

// State holds shared state between handlers.
type State struct {
	selfURL       string
	tokenFile     string
	tokenCallback string
}

// New creates a new handlers State container.
func New(url, tokenFile, tokenCallback string) *State {
	return &State{
		selfURL:       url,
		tokenFile:     tokenFile,
		tokenCallback: tokenCallback,
	}
}
