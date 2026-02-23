#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#   Copyright (C) 2006-2021 University of Dundee. All rights reserved.
#
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# ------------------------------------------------------------------------------

"""
This script converts a Dataset of Images to a Plate, with one image per Well.
"""

# @author Will Moore (adapted by Jens Wendt)
# <a href="mailto:jens.wendt@uni-muenster.de">jens.wendt@uni-muenster.de</a>
# @version 5

import omero.scripts as scripts
from omero.gateway import BlitzGateway
import omero
# try importing regex, otherwise fallback to re
try:
    import regex as re
except ImportError:
    print("regex package was not found. Falling back to the native re package."
          " If you want to utilize more advanced regular expression patterns,"
          " contact your OMERO administrator about installing the regex package.")
    import re
from collections import defaultdict

from omero.rtypes import rint, rlong, rstring, robject, unwrap

def add_images_to_plate(conn, image_dict, plate_id, remove_from=None):
    """
    Add the Images to a Plate, creating a new well at the specified column and
    row
    NB - This will fail if there is already a well at that point
    """
    update_service = conn.getUpdateService()

    for row, cols in image_dict.items():
        for col, images in cols.items():
            well = omero.model.WellI()
            well.plate = omero.model.PlateI(plate_id, False)
            well.column = rint(col)
            well.row = rint(row)
            try:
                for image_id in images:
                    ws = omero.model.WellSampleI()
                    ws.image = omero.model.ImageI(image_id, False)
                    ws.well = well
                    well.addWellSample(ws)
                update_service.saveObject(well)
            except Exception:
                return False

            # remove from Datast
            for image_id in images:
                if remove_from is not None:
                    image = conn.getObject("Image", image_id)
                    # this reads weird
                    links = list(image.getParentLinks(remove_from.id))
                    link_ids = [link.id for link in links]
                    conn.deleteObjects('DatasetImageLink', link_ids)
    return True


def dataset_to_plate(conn, script_params, dataset_id, screen):

    dataset = conn.getObject("Dataset", dataset_id)
    if dataset is None:
        return

    update_service = conn.getUpdateService()

    # create Plate
    plate = omero.model.PlateI()
    plate.name = omero.rtypes.RStringI(dataset.name)
    plate = update_service.saveAndReturnObject(plate)

    #link plate to screen if specified and possible
    if screen is not None and screen.canLink():
        link = omero.model.ScreenPlateLinkI()
        link.parent = omero.model.ScreenI(screen.id, False)
        link.child = omero.model.PlateI(plate.id.val, False)
        update_service.saveObject(link)
    else:
        link = None

    row = 0
    col = 0
    # a default dict to store the images for each well
    # in the form of {row: {column: [image1, image2, ...]}}
    image_dict = defaultdict(lambda: defaultdict(list))

    # get images from dataset
    images = list(dataset.listChildren())
    dataset_img_count = len(images)
    if "Filter_Names" in script_params:
        filter_by = script_params["Filter_Names"]
        images = [i for i in images if i.getName().find(filter_by) >= 0]

    # parse for full well expression
    if script_params["'Full'_well_expression"] and "Regular_expression_for_wells" in script_params:
        full_well_re = script_params["Regular_expression_for_wells"]
        pattern = re.compile(full_well_re)
        for image in images:
            match = pattern.findall(image.getName())
            if len(match) > 1:
                print(f"Image: {image.getName()} - had more than one match for full well expression.")
                return None, None, None
            elif len(match) == 0:
                print(f"Image: {image.getName()} - no match for full well expression.")
                return None, None, None
            elif len(match) == 1:
                full_well_str = match[0]
                row_str = re.findall(r"(?P<row>[a-pA-P])", full_well_str)[0]
                col_str = re.findall(r"(?P<column>\d{1,2})", full_well_str)[0]
                row = ord(row_str.upper()) - ord('A')
                col = int(col_str) - 1
                # store the image in the dict
                image_dict[row][col].append(image.getId())

    elif script_params["'Full'_well_expression"] and not "Regular_expression_for_wells" in script_params:
        print("If you want to use a regular expression to parse a full well expression, you need to provide a regular expression for wells.")
        return None, None, None

    elif not "Regular_expression_for_rows" in script_params or \
        not "Regular_expression_for_columns" in script_params:
        print("If you want to use regular expressions to parse row and "
              "column information, you need to provide a regular expression both for rows and columns.")
        return None, None, None
    
    # parse for row and column expressions
    elif script_params["Regular_expression_for_rows"] and script_params["Regular_expression_for_columns"]:
        row_re = script_params["Regular_expression_for_rows"]
        col_re = script_params["Regular_expression_for_columns"]
        row_pattern = re.compile(row_re)
        col_pattern = re.compile(col_re)
        for image in images:
            row_match = row_pattern.findall(image.getName())
            col_match = col_pattern.findall(image.getName())
            if len(row_match) > 1:
                print(f"Image: {image.getName()} - had more than one match for row expression.")
                return None, None, None
            elif len(row_match) == 0:
                print(f"Image: {image.getName()} - no match for row expression.")
                return None, None, None
            elif len(row_match) == 1:
                row_str = row_match[0]
                row = ord(row_str.upper()) - ord('A')

            if len(col_match) > 1:
                print(f"Image: {image.getName()} - had more than one match for column expression.")
                return None, None, None
            elif len(col_match) == 0:
                print(f"Image: {image.getName()} - no match for column expression.")
                return None, None, None
            elif len(col_match) == 1:
                col_str = col_match[0]
                col = int(col_str) - 1
                # store the image in the dict
                image_dict[row][col].append(image.getId())

    # Do we try to remove images from Dataset and Delte Datset when/if empty?
    remove_from = None
    remove_dataset = "Remove_From_Dataset" in script_params and \
        script_params["Remove_From_Dataset"]
    if remove_dataset:
        remove_from = dataset

    added_bool = add_images_to_plate(conn, image_dict, plate.id.val, remove_from)
    return plate, link

def datasets_to_plates(conn, script_params):

    update_service = conn.getUpdateService()
    message = ""
    
    # generate the list of all images
    # generate a dict with names and ID of images
    # run the regex matches to get the matches for (plate,) row, column and position
    # create dict of dicts for plate, row, column and position with the image IDs
    # generate the plates, wells and well samples based on the dict of dicts

    # Get the datasets ID
    dtype = script_params['Data_Type']
    ids = script_params['IDs']
    datasets = list(conn.getObjects(dtype, ids))

    def has_images_linked_to_well(dataset):
        params = omero.sys.ParametersI()
        query = "select count(well) from Well as well "\
                "left outer join well.wellSamples as ws " \
                "left outer join ws.image as img "\
                "where img.id in (:ids)"
        params.addIds([i.getId() for i in dataset.listChildren()])
        n_wells = unwrap(conn.getQueryService().projection(
            query, params, conn.SERVICE_OPTS)[0])[0]
        if n_wells > 0:
            return True
        else:
            return False

    # Exclude datasets containing images already linked to a well
    # Jens: Unsure why this safeguard is in here, but I decided
    # to keep it for now
    n_datasets = len(datasets)
    datasets = [x for x in datasets if not has_images_linked_to_well(x)]
    if len(datasets) < n_datasets:
        message += "Excluded %s out of %s dataset(s). " \
            % (n_datasets - len(datasets), n_datasets)

    # Return if all input dataset are not found or excluded
    if not datasets:
        return None, message

    # Filter dataset IDs by permissions
    ids = [ds.getId() for ds in datasets if ds.canLink()]
    if len(ids) != len(datasets):
        perm_ids = [str(ds.getId()) for ds in datasets if not ds.canLink()]
        message += "You do not have the permissions to add the images from"\
            " the dataset(s): %s." % ",".join(perm_ids)
    if not ids:
        return None, message

    # find or create Screen if specified
    screen = None
    newscreen = None
    if "Screen" in script_params and len(script_params["Screen"]) > 0:
        s = script_params["Screen"]
        # see if this is ID of existing screen
        try:
            screen_id = int(s)
            screen = conn.getObject("Screen", screen_id)
        except ValueError:
            pass
        # if not, create one
        if screen is None:
            newscreen = omero.model.ScreenI()
            newscreen.name = rstring(s)
            newscreen = update_service.saveAndReturnObject(newscreen)
            screen = conn.getObject("Screen", newscreen.getId().getValue())

    plates = []
    links = []
    deletes = []
    for dataset_id in ids:
        plate, link = dataset_to_plate(conn, script_params,
                                                      dataset_id, screen)
        if plate is None and link is None:
            message += f"Could not create plate from dataset {dataset_id}."
            message += "\nCheck logs for details."
            return None, message        
        if plate is not None:
            plates.append(plate)
        if link is not None:
            links.append(link)

    # wait for any deletes to finish
    for handle in deletes:
        cb = omero.callbacks.DeleteCallbackI(conn.c, handle)
        while True:  # ms
            if cb.block(100) is not None:
                break

    if newscreen:
        message += "New screen created: %s." % newscreen.getName().getValue()
        robj = newscreen
    elif plates:
        robj = plates[0]
    else:
        robj = None

    if plates:
        if len(plates) == 1:
            plate = plates[0]
            message += " New plate created: %s" % plate.getName().getValue()
        else:
            message += " %s plates created" % len(plates)
        if len(plates) == len(links):
            message += "."
        else:
            message += " but could not be attached."
    else:
        message += "No plate created."
    return robj, message


def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    data_types = [rstring('Dataset')]
    first_axis = [rstring('column'), rstring('row')]
    row_col_naming = [rstring('letter'), rstring('number')]

    client = scripts.client(
        'Dataset_To_Plate.py',
        """Take a Dataset of Images and put them in a new Plate, \
arranging them into rows or columns as desired.
Optionally add the Plate to a new or existing Screen.
See http://help.openmicroscopy.org/scripts.html
Uses regular expressions to extract the row and column information from the image names.
To test your regular expression patterns use https://regex101.com.""",

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images (only Dataset supported)",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of Dataset IDs to convert to new"
            " Plates.").ofType(rlong(0)),

        scripts.String(
            "Filter_Names", grouping="2.1",
            description="Filter the images by names that contain this value"),

        scripts.Bool(
            "'Full'_well_expression", grouping="3", optional=False, default=False,
            description="Check if you can provide a 'full' well expression "
            "in the image names.\nE.g. 'A23' or 'n08'\nIf not checked, regular"
            " expressions for rows and columns are expected."),

        scripts.String(
            "Regular_expression_for_wells", grouping="3.1", optional=True,
            description="Regular expression to extract the complete well "
            "name from the image names.E.g '(?'row'[a-pA-P])(?'column'[0|1|2]\\d{1})'"),

        scripts.String(
            "Regular_expression_for_rows", grouping="4", optional=True,
            description="Regular expression to extract the row information "
            "from the image names.E.g. 'r0(?'row'0|1|2\\d{1})_'"),

        scripts.String(
            "Regular_expression_for_columns", grouping="5", optional=True,
            description="Regular expression to extract the column information "
            "from the image names.E.g. 'c0(?'column'0|1|2\\d{1})_'"),

        scripts.String(
            "Screen", grouping="6",
            description="Option: put Plate(s) in a Screen. Enter Name of new"
            " screen or ID of existing screen"""),

        scripts.Bool(
            "Remove_From_Dataset", grouping="7", default=False,
            description="Remove Images from Dataset as they are added to"
            " Plate"),

        version="4",
        authors=["Jens Wendt", "Will Moore"],
        institutions=["University of Münster"],
        contact="jens.wendt@uni-muenster.de",
    )

    try:
        # get the script parameters 
        script_params = client.getInputs(unwrap=True)

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        # convert Dataset(s) to Plate(s). Returns new plates or screen
        new_obj, message = datasets_to_plates(conn, script_params)

        client.setOutput("Message", rstring(message))
        if new_obj:
            client.setOutput("New_Object", robject(new_obj))

    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()