// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"bufio"
	"flag"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"os/exec"
	"os/user"
	"path"
	"strings"
	"time"

	gerrit "github.com/andygrunwald/go-gerrit"
	"github.com/google/skia-buildbot/go/gitiles"
)

var repo string
var branch string
var gitCookiesPath string

func getGerritUrl() string {
	// TODO: Make this configurable?
	return "https://chromium-review.googlesource.com/"
}

func getFullRepoUrl(repo string) string {
	// TODO: Make this configurable?
	baseGitilesUrl := "https://chromium.googlesource.com"
	return fmt.Sprintf("%s/%s", baseGitilesUrl, repo)
}

// Borrowed from https://skia.googlesource.com/buildbot/+/master/go/gitauth/gitauth.go
func getCredentials(gitCookiesPath string) (string, error) {
	dat, err := ioutil.ReadFile(gitCookiesPath)
	if err != nil {
		return "", err
	}
	contents := string(dat)
	for _, line := range strings.Split(contents, "\n") {
		if strings.HasPrefix(line, "#") || line == "" {
			continue
		}
		tokens := strings.Split(line, "\t")
		domain, xpath, key, value := tokens[0], tokens[2], tokens[5], tokens[6]
		if (domain == ".googlesource.com" ||
			domain == "chromium.googlesource.com") &&
			xpath == "/" && key == "o" {
			return value, nil
		}
	}
	return "", fmt.Errorf("Git auth secret not found. Is there an entry for '.googlesource.com' in your gitcookies file?")
}

func getEditor() string {
	cmd := os.Getenv("VISUAL")
	if cmd != "" {
		return cmd
	}
	cmd = os.Getenv("EDITOR")
	if cmd != "" {
		return cmd
	}
	return "vim"
}

type changeInput struct {
	gerrit.ChangeInfo
	BaseCommit string `json:"commit,omitempty"`
}

// createChange implements/hacks support missing from gerrit library.
func createChange(client *gerrit.Client, input *changeInput) (*gerrit.ChangeInfo, *gerrit.Response, error) {
	u := "changes/"

	req, err := client.NewRequest("POST", u, input)
	if err != nil {
		return nil, nil, err
	}

	v := new(gerrit.ChangeInfo)
	resp, err := client.Do(req, v)
	if err != nil {
		return nil, resp, err
	}

	return v, resp, err
}

func doMain() error {
	// Get default location for gitcookies file.
	usr, err := user.Current()
	if err != nil {
		return err
	}
	homeDir := usr.HomeDir
	defGitCookiesFile := path.Join(homeDir, ".gitcookies")

	// Arg stuff.
	flags := flag.NewFlagSet(os.Args[0], flag.ExitOnError)
	flags.StringVar(&repo, "repo", "chromium/src", "Repo to change, eg: 'chromium/src'.")
	flags.StringVar(&branch, "branch", "master", "Branch to change.")
	//TODO: Support this.
	//issueNumFlag := flag.Int("issue-num", 0, "Existing issue to upload change to. Creates a new issue when not specified.")
	flags.StringVar(&gitCookiesPath, "git-cookies-path", defGitCookiesFile, "Path to git cookies file to use for gerrit/gitiles auth.")
	flags.Usage = func() {
		fmt.Printf("Usage: %s [OPTIONS] file-to-edit\n", os.Args[0])
		flags.PrintDefaults()
	}
	flags.Parse(os.Args[1:])

	if flags.NArg() != 1 {
		flags.Usage()
		return fmt.Errorf("Incorrect usage.")
	} else if _, err := os.Stat(gitCookiesPath); os.IsNotExist(err) {
		return fmt.Errorf("Git cookies file %s does not exist.\n", gitCookiesPath)
	}
	// TODO: Support editing multiple files. (ie: Chained editor sessions?)
	filePath := flags.Arg(0)
	_, fileName := path.Split(filePath)

	// Pull the token from the gitcookie file.
	cookie, err := getCredentials(gitCookiesPath)
	if err != nil {
		return err
	}

	// Create a client for use with gitiles' API.
	fullRepoUrl := getFullRepoUrl(repo)
	client, err := gerrit.NewClient(getGerritUrl(), nil)
	if err != nil {
		return err
	}
	client.Authentication.SetCookieAuth("o", cookie)

	// Create a temp dir to store all our temp files.
	tmpDir, err := ioutil.TempDir("", "gerredit")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmpDir)

	// Get current branch commit to avoid race updates.
	branchInfo, _, err := client.Projects.GetBranch(repo, branch)
	if err != nil {
		return err
	}

	// Fetch the contents of the file to edit from gitiles and place it in a temp file.
	// Use only the base name of the file when creating the temp file.
	// TODO: Use the full path instead so that you can edit multiple similarly named files at once.
	// eg: base/OWNERS and chrome/OWNERS
	tmpFile := path.Join(tmpDir, fileName)
	tmpFd, err := os.Create(tmpFile)
	if err != nil {
		return err
	}
	writer := bufio.NewWriter(tmpFd)
	repoClient := &http.Client{}
	gitilesRepo := gitiles.NewRepo(fullRepoUrl, gitCookiesPath, repoClient)
	if err = gitilesRepo.ReadFileAtRef(filePath, branchInfo.Revision, writer); err != nil {
		return err
	}
	writer.Flush()

	// Open the temp file in editor, then fetch its new contents.
	cmd := exec.Command(getEditor(), tmpFile)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	if err = cmd.Run(); err != nil {
		return err
	}
	newFileContentsBytes, err := ioutil.ReadFile(tmpFile)
	if err != nil {
		return err
	}
	newFileContents := string(newFileContentsBytes[:])

	// Create a temp file to hold the commit message, and add a template.
	commitMsgHeader := `# Enter a description of the change.
# This will be displayed on the codereview site.
# The first line will also be used as the subject of the review.
#--------------------This line is 72 characters long--------------------
`
	commitMsgFooter := `
Bug:`
	// Use a py file to trigger syntax highlighting of the comments.
	tmpCommitMsgFile := path.Join(tmpDir, "commit_msg.py")
	f, err := os.Create(tmpCommitMsgFile)
	if err != nil {
		return err
	}
	f.WriteString(commitMsgHeader)
	f.WriteString(commitMsgFooter)
	f.Sync()
	f.Close()

	// Open the commit message file in editor so the user can change it.
	cmd = exec.Command(getEditor(), tmpCommitMsgFile)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	if err = cmd.Run(); err != nil {
		return err
	}

	// Read the commit msg, remove the header comments, and get the first line.
	commitMsgBytes, err := ioutil.ReadFile(tmpCommitMsgFile)
	if err != nil {
		return err
	}
	commitMsg := string(commitMsgBytes[:])
	// Chop off the first 3 lines.
	// TODO: Be smarter about what text to ignore (ie: the user might manually delete the first 3 lines).
	commitMsgLines := strings.Split(commitMsg, "\n")[4:]
	commitMsgHeader = commitMsgLines[0]
	commitMsg = strings.Join(commitMsgLines, "\n")
	commitMsg = strings.TrimSpace(commitMsg)

	change := changeInput{
		ChangeInfo: gerrit.ChangeInfo{
			Project: repo,
			Branch:  branch,
			Subject: commitMsgHeader,
		},
		BaseCommit: branchInfo.Revision,
	}

	// The remained will take a while, so start a thread that prints dots to the console.
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	dotPrinterDone := make(chan bool)
	fmt.Printf("Uploading the change to Gerrit")
	go func() {
		for {
			select {
			case <-dotPrinterDone:
				return
			case _ = <-ticker.C:
				fmt.Printf(".")
			}
		}
	}()

	// Create a new gerrit issue.
	newCh, _, err := createChange(client, &change)
	if err != nil {
		return err
	}

	// Change the full commit message.
	commitMsg = fmt.Sprintf("%s\nChange-Id: %s", commitMsg, newCh.ChangeID)
	msgBody := gerrit.ChangeEditMessageInput{Message: commitMsg}
	_, err = client.Changes.ChangeCommitMessageInChangeEdit(newCh.ID, &msgBody)
	if err != nil {
		return err
	}

	// Add the file change to the issue.
	_, err = client.Changes.ChangeFileContentInChangeEdit(newCh.ID, filePath, newFileContents)
	if err != nil {
		return err
	}

	// Publish the change.
	_, err = client.Changes.PublishChangeEdit(newCh.ID, "NONE")
	if err != nil {
		return err
	}

	// TODO: Print link to new gerrit change.
	dotPrinterDone <- true
	url := fmt.Sprintf("%s%d", getGerritUrl(), newCh.Number)
	fmt.Printf(" Done!\n")
	fmt.Printf("New Gerrit issue located at:\n%s\n", url)
	return nil
}

func main() {
	err := doMain()
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	os.Exit(0)
}
