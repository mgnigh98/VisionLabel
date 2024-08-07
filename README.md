# VisionLabel
A tool for labeling png, jpg, and ntf/nitf files

Most functions with checkboxes will work when moving to the previous/next image
    Export Chip Grid Notably will not

Remove Image will delete the image along with txt files with the same name and any files where file_path.replace('static','moving') is true

Export Rectangles TXT and Import Bounding Boxes will work together where it will create the TXT file and read from it if both options are selected

Export Shapes will export bounding Boxes and Lines


Common shortcuts:
Left/Right Arrow Keys: Previous/Next Image

Left Click: Pan or Draw Based on the Radio Option
Right Click: Remove Most Recent Bounding Box

Middle Click: Switch Between Pan and Draw Box

0-9 Num Keys: Set number of Class Label
Up/Down Arrow Keys: Increment/Decrement Class Label




