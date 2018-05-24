// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/**
 * <cuic-single-comment> displays and allows editing and deletion of a comment.
 * @customElement
 */
class SingleComment extends ElementBaseWithUrls {

  static get is() {return 'cuic-single-comment';}

  static get properties() {
    return {
      screenshotkey: String,
      comment: Object,
      editing: {
        type: Boolean,
        value: false
      },
      editText: String
    };
  }

  deleteComment_(e) {
    this.$['delete-comment'].generateRequest();
  }

  handleDeleteResponse_(e) {
    // Update displayed comments
    this.updateDisplay_();
  }

  handleDeleteError_(e) {
    alert('Error deleting comment')
    console.log('Error deleting comment');
    console.log(e.detail);
    // Update displayed comments
    this.updateDisplay_();
  }

  saveEdit_(e) {
    this.$['edit-comment'].generateRequest();
    this.set('editing', false);
  }

  cancelEdit_(e) {
    this.set('editing', false);
  }

  editComment_(e) {
    this.set('editText', this.comment.text);
    this.set('editing', true);
  }

  handleEditResponse_(e) {
    // Update displayed comments
    this.updateDisplay_();
  }

  handleEditError_(e) {
    alert('Error editing comment')
    console.log('Error editing comment');
    console.log(e.detail);
    // Update displayed comments
    this.updateDisplay_();
  }

  updateDisplay_(){
    this.dispatchEvent(new CustomEvent('comments-changed'));
  }
}

window.customElements.define(SingleComment.is, SingleComment);
