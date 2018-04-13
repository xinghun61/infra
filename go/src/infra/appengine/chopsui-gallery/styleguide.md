# ChOps UI Style Guide

## Margins and padding

- For inline elements, use `em` for vertical margins and padding, and `px` for horizontal margins and padding, where the values of `px` are powers of two.

```css
span {
  padding: 1em 16px;
}
```

## Responsive Design

- For breakpoints, use one of the values [defined by Material design](https://material.io/guidelines/layout/responsive-ui.html).
- Acceptable breakpoint values are one of `480, 600, 840, 960, 1280, 1440, 1600`.
