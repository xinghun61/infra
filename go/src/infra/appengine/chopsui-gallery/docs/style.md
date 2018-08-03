# ChopsUI Style Guide

ChopsUI's style guidelines are meant to be a lightweight subset of
[Material Design](https://material.io/)'s guidelines with a few additional rules to
make the style choices work better for the developer tool frontends that
Chrome Operations maintains. We want to focus on keeping our rules simple and
easy to follow.

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

## Color Codes

- For ChopsUI, we define colors with the HSL/HSLA (color space) format instead of
hex codes. HSL is generally easier than hex codes for humans to reason about,
so this format allows us to quickly tweak colors on the fly.

```css
span {
  background-color: hsl(207, 90%, 54%);
}
```

## Color

- For ChopsUI, we recommend using a subset of the [Material Design color palette](https://material.io/guidelines/style/color.html#color-color-palette).
- We recommend using more neutral/less bright colors for large areas of colors and
saving brighter colors for places where color is used semantically.
