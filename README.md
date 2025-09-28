# Smooth Quad Triangulation

This is a Blender add-on for triangulating quad faces to create smoother geometry.

<img src="https://github.com/user-attachments/assets/7a7b61e3-cedf-4c18-a0ea-001a8910ddd7" alt="Example: before and after" width="50%" />
<img src="https://github.com/user-attachments/assets/7132acde-fac6-4b78-be60-7418b43c060d" alt="Example: topology" />

## Requirements

- Blender 2.93 or later

## Installation

1. Download the `.zip` file from the [releases](../../releases) page.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click `Install from Disk` and select the downloaded `.zip` file.

## Usage

1. Enter Edit Mode and select the quad faces you want to triangulate.
2. Open the `Face` menu and choose `Smooth Quad Triangulation`.

## Limitations

- Only quad faces are supported; N-gons are ignored.
- Does not ensure topological cleanliness.
- Best suited for curved, organic shapes. Not recommended for flat or hard-surface models.
