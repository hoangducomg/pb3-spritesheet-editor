# Plazma Burst 3 Animate Frame Editor
• Plazma Burst 3 Animate Frame Editor is a desktop tool for turning images, folders, GIFs, and videos into a sprite sheet and a ready-to-paste pb2Decoration.CreateDecoration block for your game.

## Features
• Inputs: load a folder, several selected images, a GIF, or a video.
• Compress & Rescale: rescale by percentage or exact W x H, crop, auto-trim transparent edges, resample (nearest, bilinear, Lanczos), flip and rotate.
• Optimize: merge duplicate frames into hold counts, remove every n-th frame, quantize colors to 256.
• Sequence editor: reorder, duplicate, delete, and set hold times per frame, with live preview and play/pause.
• Animations: define several named animations as ranges of the sheet, each with its own speed, loop, and report-end setting.
Decoration properties: X, Y, Z, scaleX/Y/Z, offsets, frame offsets, starting frame and progress, speed, timescale, animation id, pixelated, static, start playing, and timing relative to world.

## Outputs
• Packed sprite sheet saved as WebP (lossless or with a quality slider), with a configurable number of columns.
Generated pb2Decoration code, which you can copy or save as a .js file.
• Save a single selected frame, or all frames to a folder, as PNG.

## Requirements
• Windows, macOS, or Linux
• Python 3.9 or newer
• Pillow
• OpenCV (only needed for video input)

## Installation
• Step 1: Double click on `setup.bat` to install. It should be in the same folder as `PB3 Animate Frames Editor.py`
The script checks for Python, creates a .venv folder, installs Pillow and OpenCV, and starts the app. Delete .venv to reset the environment.

## How to use
• Load frames, pick your input files.
• Process, set rescale, crop, resize, optimize if needed.
• Edit the sequence if needed.
• Set decoration properties, later can be change in game instead if you know how to read .js code.
• Build and export | save sprite sheet as .webp | save or copy the .js code and paste in code snippet

## Output
• Sprite sheet: Frames are laid out row by row, left to right, top to bottom. Each cell uses the largest frame's width and height, and smaller frames are centered. Hold values repeat a frame in the sheet. The Sheet columns setting controls how many cells appear per row; 0 puts everything in one row.
• Generated .js code: The output looks like this:

``
// ::For A Better Experience::
var decoration = pb2Decoration.CreateDecoration({
	source: 'user_data.UID',
	x: 0,
	y: 0,
	z: 0,
	scaleX: 0,
	...
	animations:
	[
		{ // 0: idle
			firstFrame: 0,
			frameCount: ...
		}
	]
});
``

## Notes
• scaleX, scaleY, and scaleZ default to 0. If your engine treats 0 as "no scale", set them to 1.
• Saved frames are PNG, so transparency is kept. The sprite sheet is WebP.
• If WebP saving fails, run pip install -U pillow to get a build with WebP support.
• Animation ranges must stay within the sheet. The app reports an error if first + count goes past the last cell.
• Sometimes the game decided to resize your output sprite sheet, which cause inaccuracy between frame transitioning. Keep your sprite sheet image as close as 1:1 ratio (maximum 1500x1500) as possible.
• If the output are not working, check, by default, scaleXYZ are set to 0.

## Disclaimer
• The program are written by Claude AI. As an AI generated program. The program are free to use, as a free, open source project.
