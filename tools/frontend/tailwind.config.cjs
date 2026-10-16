const tailwind = {};

    tailwind.config = {
      darkMode: "class",
      theme: {
        extend: {
          "colors": {
            "on-primary-fixed-variant": "#264191",
            "surface-tint": "#4059aa",
            "on-primary-container": "#90a8ff",
            "on-surface-variant": "#444651",
            "on-secondary-fixed-variant": "#3c475a",
            "secondary-fixed": "#d8e3fb",
            "on-tertiary-fixed-variant": "#004b73",
            "surface-container": "#eceef0",
            "primary": "#00236f",
            "surface": "#f7f9fb",
            "inverse-primary": "#b6c4ff",
            "tertiary-fixed": "#cce5ff",
            "outline-variant": "#c5c5d3",
            "error-container": "#ffdad6",
            "on-primary": "#ffffff",
            "background": "#f7f9fb",
            "outline": "#757682",
            "secondary-container": "#d5e0f8",
            "tertiary-container": "#004469",
            "surface-variant": "#e0e3e5",
            "primary-fixed": "#dce1ff",
            "secondary-fixed-dim": "#bcc7de",
            "inverse-on-surface": "#eff1f3",
            "primary-container": "#1e3a8a",
            "on-error-container": "#93000a",
            "on-secondary": "#ffffff",
            "surface-dim": "#d8dadc",
            "surface-bright": "#f7f9fb",
            "on-tertiary-container": "#56b3f9",
            "error": "#ba1a1a",
            "primary-fixed-dim": "#b6c4ff",
            "on-primary-fixed": "#00164e",
            "on-background": "#191c1e",
            "tertiary-fixed-dim": "#93ccff",
            "on-secondary-container": "#586377",
            "surface-container-highest": "#e0e3e5",
            "on-surface": "#191c1e",
            "on-secondary-fixed": "#111c2d",
            "surface-container-high": "#e6e8ea",
            "on-tertiary": "#ffffff",
            "on-error": "#ffffff",
            "surface-container-lowest": "#ffffff",
            "on-tertiary-fixed": "#001d31",
            "surface-container-low": "#f2f4f6",
            "tertiary": "#002d48",
            "inverse-surface": "#2d3133",
            "secondary": "#545f73"
          },
          "borderRadius": {
            "DEFAULT": "0.125rem",
            "lg": "0.25rem",
            "xl": "0.5rem",
            "full": "0.75rem"
          },
          "spacing": {
            "gutter-sm": "0.75rem",
            "margin-sm": "1rem",
            "margin-lg": "2.5rem",
            "space-lg": "1.25rem",
            "space-xs": "0.25rem",
            "space-xl": "1.75rem",
            "space-md": "0.75rem",
            "gutter": "1.25rem",
            "gutter-lg": "1.5rem",
            "space-sm": "0.5rem",
            "margin": "1.5rem"
          },
          "fontFamily": {
            "headline-xl": ["Inter"],
            "label-md": ["Inter"],
            "label-sm": ["Inter"],
            "body-lg": ["Inter"],
            "headline-lg": ["Inter"],
            "caption": ["Inter"],
            "body-md": ["Inter"],
            "body-sm": ["Inter"],
            "data-tabular": ["Inter"],
            "headline-xl-mobile": ["Inter"],
            "headline-sm": ["Inter"],
            "headline-md": ["Inter"]
          },
          "fontSize": {
            "headline-xl": ["32px", { "lineHeight": "40px", "letterSpacing": "-0.02em", "fontWeight": "700" }],
            "label-md": ["13px", { "lineHeight": "18px", "letterSpacing": "0.01em", "fontWeight": "600" }],
            "label-sm": ["12px", { "lineHeight": "16px", "letterSpacing": "0.02em", "fontWeight": "500" }],
            "body-lg": ["16px", { "lineHeight": "24px", "letterSpacing": "0em", "fontWeight": "400" }],
            "headline-lg": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.015em", "fontWeight": "600" }],
            "caption": ["11px", { "lineHeight": "14px", "letterSpacing": "0.03em", "fontWeight": "500" }],
            "body-md": ["14px", { "lineHeight": "20px", "letterSpacing": "0em", "fontWeight": "400" }],
            "body-sm": ["13px", { "lineHeight": "18px", "letterSpacing": "0.005em", "fontWeight": "400" }],
            "data-tabular": ["13px", { "lineHeight": "18px", "letterSpacing": "0em", "fontWeight": "500" }],
            "headline-xl-mobile": ["26px", { "lineHeight": "34px", "letterSpacing": "-0.015em", "fontWeight": "700" }],
            "headline-sm": ["16px", { "lineHeight": "24px", "letterSpacing": "-0.005em", "fontWeight": "600" }],
            "headline-md": ["20px", { "lineHeight": "28px", "letterSpacing": "-0.01em", "fontWeight": "600" }]
          }
        }
      }
    }
  
module.exports = {...tailwind.config, content:{relative:true, files:["../../templates/**/*.html"]}, corePlugins:{preflight:false}, plugins:[require("@tailwindcss/forms")]};