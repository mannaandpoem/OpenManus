# OpenManus Web Directory

This directory contains the web interface related files for OpenManus.

## Directory Structure

```
web/
  ├── static/          - Static resource files
  │   ├── css/         - Style files
  │   ├── js/          - JavaScript files
  │   ├── logo/        - Logos and icons
  │   └── themes/      - Theme folders
  │       ├── openmanus/    - Default theme
  │       └── cyberpunk/    - Cyberpunk theme
  └── templates/       - HTML template files
      └── index.html   - Homepage template
```

## Theme System

### Theme Structure

Each theme must follow this file structure:

```
themes/theme_name/
  ├── static/
  │   ├── style.css  (required)
  │   └── ...        (other static resources)
  ├── templates/
  │   └── chat.html  (required)
  └── theme.json     (required)
```

### How to Add a New Theme

1. Create a new folder in the `web/static/themes` directory with your theme name
2. Copy the `static` and `templates` folder structure
3. Create a `theme.json` file with the following content:

```json
{
    "name": "Theme Display Name",
    "description": "Brief description of the theme",
    "author": "Author Name",
    "version": "1.0.0"
}
```

4. Modify the CSS and HTML files to achieve the look you want

### Path References

In theme HTML files, make sure to use the following path format to reference resources:

```html
<link rel="stylesheet" href="/static/themes/your_theme_name/static/your_theme.css">
<script src="/static/js/main.js"></script>
```

## Development Notes

All web-related static files and templates are located in this directory. The application will load resources from this directory, not from the project root.

When modifying application code, make sure all path references point to the correct file locations in the web directory.

## Existing Themes

- `openmanus`: Default theme
- `cyberpunk`: Cyberpunk theme

When you add a new theme, the system will automatically display it as an option on the homepage.
