# OMERO utility scripts

This is a hodgepodge of different utility scripts for OMERO.web, all run on the University Münster OMERO [instance](https://omero-imaging.uni-muenster.de/webclient/).

From very simple things, e.g. setting the pixel size, to more complicated stuff like specific adaptations of the vanilla `Dataset_To_Plate.py` script.

There is (almost) no common style as these scripts stem from different timepoints in my career at Uni Münster and reflect different skill levels.

For the beginning every script will have its README.md combined into this main one.

## SetPixelSize
Very simple OMERO.web script that is capable of setting pixel sizes for X, Y and Z dimensions of OMERO Images. It can iterate over all Images in an OMERO Project, Dataset, Screen or Plate.

The User can decide if existing values get overwritten. By default they will be. If no pixel size exists for a dimension, it will always be set to a new given value.

Values for X, Y and Z can be set independently. By default, if a value for X is set, it will be used for Y and Z as well.

If an Image does not have more than one Z-stack the pixel size for Z will not be set even if a value is given.

## Dataset to Plate (generic)
An adaptation of the original `Dataset to Plate` script which utilizes regular expressions to parse out the respective well of an image.

It tries to import the `regex` package, but will fall back to the native `re` package if not found.

The logic of associating images with wells has also been adapted, now allowing for wells with a different number of images.

## Rename Images
A script utilizing regex to modify image names.

Admins can pre-specify patterns that can be easily selected by the end-user via dropdown menu. A simple config.json file on the server is used for that. The path has to be adjusted in the script before the upload, and the file readable for the `omero-server` user.<br>
The script is able to parse the original metadata which is stored as key-value pairs
in OMERO and extract values from keys which match the regex pattern. The values extracted are then being matched via a named capture group `index` which has to be in both regex patterns.<br>
#### Example:<br>
The image names are **"larvae_12x.czi[Scene #1..15]"** and in the original metadata the value that we want to replace "Scene #1" with is behind the key **Information|Image|S|Scene|Name #1..15 = xxxx**.<br>
`Pattern_to_be_replaced` would have to be **Scene #(?P\<index>\\d+)** and `Replacement_Pattern` **Information\\|Image\\|S\\|Scene\\|Name #(?P\<index>\\d+)**<br>
The script than parses all the values from the matching keys of the original metadata and replaces them based on the `index` capture group with corresponding regex match in the image name.

If a custom pattern is needed. Users simply select `Custom_Pattern` in the dropdown menu and click the `Custom Pattern` checkbox. Then they can choose to use simple literal replacement patterns or regex based patterns via the `Regex Pattern` checkbox. This will not utilize the original metadata (for now).