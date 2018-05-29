// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

class ShotSelector extends Polymer.Element {
  static get is() {
    return 'cuic-shot-selector';
  }

  static get properties() {
    return {
      selection: {
        type: Object,
        observer: 'updateMenus_',
        notify: true,
        value() {
          return {filters: {}, userTags: []}
        }
      },
      menuEntries_: Array,
      userTagNames_: Array,
      newTag_: {
        type: String,
        observer: 'newTagChanged_'
      },
      newTagSelector_: {
        type: Number,
        value: -1,
        notify: true
      },
      userTagMenuFocused_: Boolean,
      leftButtonVisible_: Boolean,
      rightButtonVisible_: Boolean
    };
  }

  static get observers() {
    return [
      'menuSelectionChanged_(menuEntries_.*)',
      'userTagCheckChanged_(userTags_.*)'
    ];
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('resize', e => {
      clearTimeout(this.resizeTimeout);
      this.resizeTimeout = setTimeout(this.updateScrollButtons_(), 100);
    });
  }

  menuSelectionChanged_(menuItem) {
    if (menuItem) {
      const filters = menuItem.base.reduce((filters, item) => {
        if (item.selection !== 0) {
          filters[item.title] = item.values[item.selection];
        }
        return filters;
      }, {});
      if (JSON.stringify(filters) !== JSON.stringify(this.selection.filters)) {
        this.set('selection.filters', filters);
      }
    }
    const userTagNames = this.$['tag-set'].taglist.userTags.filter(
        t => (!this.selection.userTags.includes(t))).sort();
    this.set('userTagNames_', userTagNames);
  }

  sortArray_(array, f) {
    array.sort((a, b) => {
      const fa = f(a);
      const fb = f(b);
      if (fa < fb) return -1;
      if (fa > fb) return 1;
      return 0;
    });
  }

  updateMenus_() {
    if (!this.filterlist_) return;
    const menuEntries = Object.keys(this.filterlist_).map(filterName => {
      const selectedEntry = this.selection.filters[filterName];
      const v = this.filterlist_[filterName].slice();
      this.sortArray_(v, t => t.toUpperCase());
      if (v.length > 1) {
        v.unshift('Any');
      }
      return {
        title: filterName,
        values: v,
        selection: (selectedEntry && v.indexOf(selectedEntry) >= 0) ?
            v.indexOf(selectedEntry) :
            0
      };
    });
    this.sortArray_(menuEntries, t => t.title.toUpperCase());
    this.set('menuEntries_', menuEntries);
  }

  userTagCheckChanged_(e) {
    var selectedTags = this.userTags_.filter(t => t.checked).map(t => t.title);
    if (selectedTags.length !== this.selection.userTags.length) {
      this.set('selection.userTags', selectedTags);
    }
  }

  handleTagChange_(e) {
    this.filterlist_ = this.$['tag-set'].taglist.filters;
    const filters = this.selection.filters;
    for (var filterName in Object.keys(this.filterlist_)) {
      if(!filters[filterName]) {
        filters[filterName] = 0;
      }
    }
    const selectedTags = this.selection.userTags;
    const userTagNames = this.$['tag-set'].taglist.userTags.filter(t =>
        (!selectedTags.includes(t))).sort();
    this.set('userTagNames_', userTagNames);
    this.updateMenus_();
    const tagsListRect = this.$['tags-list'].getBoundingClientRect();
    if (tagsListRect.width <= this.documentWidth_() || tagsListRect.left > 0) {
      this.setLeftPos_(0);
    }
    this.updateScrollButtons_()
  }

  updateScrollButtons_() {
    window.requestAnimationFrame(t=>{
      const tagsListRect = this.$['tags-list'].getBoundingClientRect();
      if (tagsListRect.width <= this.documentWidth_()) {
          this.set('rightButtonVisible_', false);
          this.set('leftButtonVisible_', false);
      } else {
        this.set('rightButtonVisible_',
            tagsListRect.right > this.documentWidth_());
        this.set('leftButtonVisible_', tagsListRect.left < 0);
      }
    });
  }

  // Extracted so that it can be overridden for testing
  documentWidth_() {
    return document.documentElement.clientWidth;
  }

  newTagMenuFocusChange_() {
    this.set('newTagSelector_', -1);
  }

  newTagChanged_(e) {
    if (this.userTagMenuFocused_ && this.newTag_) {
      this.push('selection.userTags', this.newTag_);
      this.splice('userTagNames_', this.userTagNames_.indexOf(this.newTag_), 1);
    }
    this.updateScrollButtons_();
  }

  removeTagTapped_(e) {
    this.splice('selection.userTags', e.model.index, 1);
    // Keep userTagNames_ sorted
    const insertIndex = this.userTagNames_.findIndex(s => (s > e.model.item))
    if (insertIndex === -1) {
      this.push('userTagNames_', e.model.item)
    } else {
      this.splice('userTagNames_', insertIndex, 0, e.model.item);
    }
    this.updateScrollButtons_();
  }

  setLeftPos_(pos) {
    this.$['tags-list'].style.left = pos.toString() + 'px';
  }

  rightScrollButtonPressed_() {
    const tagsListRect = this.$['tags-list'].getBoundingClientRect();
    const leftPos = tagsListRect.left - document.documentElement.clientWidth/2;
    this.setLeftPos_(leftPos);
    this.updateScrollButtons_();
  }

  leftScrollButtonPressed_() {
    let leftPos = this.$['tags-list'].getBoundingClientRect().left;
    leftPos += document.documentElement.clientWidth/2;
    if (leftPos > 0) {
      leftPos = 0;
    }
    this.setLeftPos_(leftPos);
    this.updateScrollButtons_();
  }
}


window.customElements.define(ShotSelector.is, ShotSelector);
