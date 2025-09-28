# Smooth Quad Triangulation

This is a Blender add-on for triangulating quad faces to create smoother geometry.

<img src="https://github.com/user-attachments/assets/7ed8984d-dae6-4959-a02f-2c058129eaa3" alt="Example: before and after" width="50%" />
<img src="https://github.com/user-attachments/assets/fc20e828-a896-48e5-9d20-806c031deffe" alt="Example: topology" />

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
