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