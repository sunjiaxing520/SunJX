# SunJX Personal Blog

A dark editorial personal developer blog built with React, TypeScript, Vite, and lucide-react.

## Sections

- Hero introduction with project visual asset
- Local editor for changing content in the browser
- Upload controls for the hero image and project images
- 3D globe album with editable place markers, location photo uploads, and marker cover images
- Selected work / portfolio cards
- Writing and build-log list
- About, capabilities, skills, and timeline
- Contact links

## Scripts

```bash
npm install
npm run dev
npm run build
```

## Notes

Click the `编辑` button in the top navigation to open the local editor. Edits and uploaded images are saved to browser `localStorage`, so they persist after refresh on the same browser. Use `恢复默认` in the editor to clear local changes and return to the default content.

The 3D globe album editor supports adding places, adjusting each marker's position with X/Y sliders, uploading multiple images for a place, and choosing one image as the marker cover. Drag the globe to rotate, scroll to zoom, and click a marker on the globe to view that place's album.

The current content is placeholder-friendly and can be replaced with real case studies, essays, GitHub links, and contact details as they become available.
