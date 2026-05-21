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
This script will rename images according to a generic pattern or a pattern pre-defined in a custom configuration file.
"""

# @author Jens Wendt
# <a href="mailto:jens.wendt@uni-muenster.de">jens.wendt@uni-muenster.de</a>
# @version 0.2
try:
    import regex as re
except ImportError:
    import re # fallback to built-in re if regex is not available, but this will limit functionality
    print("The 'regex' module is required for this script. " \
    "The scripts falls back to the built-in 're' module.")

import json
import omero.scripts as scripts
from omero.gateway import BlitzGateway

# special imports
from omero.rtypes import rlong, rstring

CONFIG_PATH = "/opt/omero/MiN_Rename_Images_config.json"


def collect_images(conn, data_type, ids):
    """
    Collect image objects from the selected source type and IDs.
    """
    images = []

    if data_type == "Image":
        images = list(conn.getObjects("Image", ids))

    elif data_type == "Dataset":
        for dataset in conn.getObjects("Dataset", ids):
            images.extend(list(dataset.listChildren()))

    elif data_type == "Project":
        for project in conn.getObjects("Project", ids):
            for dataset in project.listChildren():
                images.extend(list(dataset.listChildren()))

    elif data_type == "Plate":
        for plate in conn.getObjects("Plate", ids):
            for well in plate.listChildren():
                for well_sample in well.listChildren():
                    image = well_sample.getImage()
                    if image is not None:
                        images.append(image)

    elif data_type == "Screen":
        for screen in conn.getObjects("Screen", ids):
            for plate in screen.listChildren():
                for well in plate.listChildren():
                    for well_sample in well.listChildren():
                        image = well_sample.getImage()
                        if image is not None:
                            images.append(image)

    return images


def extract_match_index(regex_match):
    """
    Extract index from named capture group 'index' only.
    If that group is not present or not matched, index-based matching is disabled.
    """
    named_index = regex_match.groupdict().get("index")
    if named_index is None:
        return None
    return str(named_index)


def extract_index_from_metadata_key(metadata_key):
    """
    Extract trailing '#<number>' from a metadata key when present.
    """
    fallback = re.search(r"#\s*(\d+)\s*$", metadata_key)
    if fallback:
        return fallback.group(1)
    return None


def resolve_replacement_value(regex_match, replacement_pattern, metadata,
                               metadata_key_pattern=None, shared_group_names=None):
    """
    Resolve replacement value from original metadata.
    Tries exact key lookup first, then named-group matching against metadata keys,
    and finally falls back to legacy index-based matching.
    """
    direct_value = metadata.get(replacement_pattern)
    if direct_value is not None:
        return direct_value

    if metadata_key_pattern is not None and shared_group_names:
        source_named_groups = regex_match.groupdict()

        for metadata_key, metadata_value in metadata.items():
            key_match = metadata_key_pattern.fullmatch(metadata_key)
            if key_match is None:
                continue

            key_named_groups = key_match.groupdict()
            matches_all_shared_groups = True
            for group_name in shared_group_names:
                source_value = source_named_groups.get(group_name)
                key_value = key_named_groups.get(group_name)
                if source_value is None or key_value is None or source_value != key_value:
                    matches_all_shared_groups = False
                    break

            if matches_all_shared_groups:
                return metadata_value

    index = extract_match_index(regex_match)
    if index is None:
        return None

    # Legacy support: treat replacement_pattern as key prefix and append " #<index>".
    metadata_key = f"{replacement_pattern} #{index}"
    indexed_value = metadata.get(metadata_key)
    if indexed_value is not None:
        return indexed_value

    # Additional compatibility: if replacement_pattern is a regex with at least one
    # capture group, match metadata keys and compare first group against extracted index.
    if metadata_key_pattern is not None:
        for metadata_key, metadata_value in metadata.items():
            key_match = metadata_key_pattern.fullmatch(metadata_key)
            if key_match is None:
                continue

            key_index = key_match.groupdict().get("index")
            if key_index is not None and key_index == index:
                return metadata_value

            key_groups = key_match.groups()
            if key_groups and key_groups[0] == index:
                return metadata_value

    return None


def print_metadata_index_debug(image, index, replacement_pattern, metadata,
                               metadata_key_pattern=None):
    """
    Print detailed debug information for index-based metadata matching.
    """
    print(
        f"DEBUG: Missing metadata index match for image ID {image.getId()} "
        f"('{image.getName()}'), requested index='{index}'."
    )
    print(f"DEBUG: Replacement_Pattern='{replacement_pattern}'")

    if metadata_key_pattern is None:
        print("DEBUG: Replacement_Pattern could not be compiled as regex.")

    print(f"DEBUG: Original metadata entries: {len(metadata)}")
    for metadata_key, metadata_value in metadata.items():
        key_match = None
        key_index = None
        if metadata_key_pattern is not None:
            key_match = metadata_key_pattern.fullmatch(metadata_key)
            if key_match is not None:
                key_index = key_match.groupdict().get("index")
                if key_index is None:
                    key_groups = key_match.groups()
                    if key_groups:
                        key_index = key_groups[0]

        fallback_index = extract_index_from_metadata_key(metadata_key)
        if key_match is not None or fallback_index is not None:
            print(
                "DEBUG: "
                f"key='{metadata_key}' value='{metadata_value}' "
                f"regex_match={key_match is not None} "
                f"regex_index='{key_index}' fallback_index='{fallback_index}'"
            )

def get_original_metadata(image_id, conn):
    """
    Returns the original metadata of the image as a dictionary.
    This corresponds to the 'StructuredAnnotations' of the 
    image.
    
    Returns:
        series_metadata_dict: A dictionary containing the original metadata.
    """
    image = conn.getObject("Image", image_id)
    f, series_metadata, g_m = image.loadOriginalMetadata()
    # convert the list of tuples to a dictionary for easier access
    series_metadata_dict = {key: value for key, value in series_metadata}

    return series_metadata_dict




#################
# MAIN FUNCTION #
#################

def set_new_names(conn, script_params, specification):
    """
    This function sets new names for the images according to the specified pattern.
    The pattern can be a predefined pattern from the configuration file or a custom pattern specified by the user.

    Args:
        conn: The BlitzGateway connection object.
        script_params: The parameters passed to the script by the client.
        specification: The renaming specification from the configuration file.
    Returns:
        message: A message indicating the result of the renaming process.
        image_counter: The number of images that were renamed.
    """

    if script_params["Custom_Pattern"] and script_params["Specification"] == "Custom_Pattern":
        pattern_to_be_replaced = script_params["Pattern_to_be_replaced"]
        replacement_pattern = script_params["Replacement_Pattern"]
        regex_pattern = script_params.get("Regex_Pattern", True)
    else:
        pattern_to_be_replaced = specification["Pattern_to_be_replaced"]
        replacement_pattern = specification["Replacement_Pattern"]
        # Config option uses "Regex"; fall back to script parameter for compatibility.
        regex_pattern = specification.get("Regex")
        if regex_pattern is None:
            regex_pattern = script_params.get("Regex_Pattern", True)

    if pattern_to_be_replaced is None:
        raise ValueError("Pattern to be replaced cannot be None.")
    if replacement_pattern is None:
        raise ValueError("Replacement pattern cannot be None.")

    effective_pattern_to_be_replaced = pattern_to_be_replaced
    if not regex_pattern:
        # Treat pattern as plain text by escaping regex metacharacters.
        effective_pattern_to_be_replaced = re.escape(pattern_to_be_replaced)

    images = collect_images(conn, script_params["Data_Type"], script_params["IDs"])
    image_counter = 0
    warnings = []

    try:
        compiled_pattern = re.compile(effective_pattern_to_be_replaced)
    except re.error as err:
        raise ValueError(f"Invalid regex pattern '{effective_pattern_to_be_replaced}': {err}")

    if "(?P<index>" in replacement_pattern and "|" in replacement_pattern and r"\|" not in replacement_pattern:
        print(
            "WARNING: Replacement_Pattern contains unescaped '|'. In regex this means alternation. "
            "If metadata keys contain literal pipes, escape them as '\\|'."
        )

    compiled_replacement_key_pattern = None
    shared_group_names = set()
    try:
        compiled_replacement_key_pattern = re.compile(replacement_pattern)
        shared_group_names = set(compiled_pattern.groupindex).intersection(
            compiled_replacement_key_pattern.groupindex
        )
    except re.error:
        compiled_replacement_key_pattern = None

    for image in images:
        old_name = image.getName()
        regex_match = compiled_pattern.search(old_name)
        if regex_match is None:
            continue

        metadata = get_original_metadata(image.getId(), conn)
        resolved_value = resolve_replacement_value(
            regex_match,
            replacement_pattern,
            metadata,
            metadata_key_pattern=compiled_replacement_key_pattern,
            shared_group_names=shared_group_names
        )

        if resolved_value is not None:
            new_name = compiled_pattern.sub(resolved_value, old_name, count=1)
        else:
            index = extract_match_index(regex_match)
            if index is not None:
                print_metadata_index_debug(
                    image,
                    index,
                    replacement_pattern,
                    metadata,
                    metadata_key_pattern=compiled_replacement_key_pattern,
                )
                warning = (
                    f"Could not rename image ID {image.getId()} ('{old_name}'): "
                    f"no metadata key matched index '{index}'."
                )
                print(f"WARNING: {warning}")
                warnings.append(warning)
                continue

            new_name = compiled_pattern.sub(replacement_pattern, old_name, count=1)

        if new_name != old_name:
            image.setName(new_name)
            image.save()
            image_counter += 1

    message = "Unified replacement mode."
    if warnings:
        message += f" Skipped {len(warnings)} image(s) because no index-based metadata match was found."
        max_details = 10
        details = " | ".join(warnings[:max_details])
        if len(warnings) > max_details:
            details += f" | ... and {len(warnings) - max_details} more."
        message += f" Details: {details}"

    return message, image_counter

        

def run_script():
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    # get the correct config
    with open(CONFIG_PATH) as f:
        config_json = json.load(f)

    data_types = [rstring('Project'),rstring('Dataset'), rstring('Image'),rstring('Plate'),rstring('Screen')]
    config_options = list(config_json.keys())

    client = scripts.client(
        'Rename_Images.py',
        """
        This script will rename images according to a generic pattern\nor a pattern pre-defined in a custom configuration file.\n
        The predefined patterns are able to parse the original metadata of the images, which is stored in the 'StructuredAnnotations' of the image,\n
        and extract relevant information for the renaming.        
        """,

        scripts.String(
            "Data_Type", optional=False, grouping="1",
            description="Choose source of images",
            values=data_types, default="Dataset"),

        scripts.List(
            "IDs", optional=False, grouping="2",
            description="List of IDs"
            " Plates.").ofType(rlong(0)),

        scripts.String(
            "Specification", grouping="3", values=config_options, optional=False,
            description="Select a configuration for the renaming pattern. If 'Custom_Pattern' is selected, " \
            "the user can specify a custom regex pattern to replace  in the image names below."),

        scripts.Bool(
            "Custom_Pattern", grouping="4", optional=False, default=False),

        scripts.Bool(
            "Regex_Pattern", grouping="4.1", optional=False, default=False,
            description="Will the patterns be Regex patterns?\nTo try out Regex patterns, utilize regex101.com."),

        scripts.String(
            "Pattern_to_be_replaced", grouping="4.2", optional=True, default="[a-zA-Z]+_[a-zA-Z]+(?=_)",
            description="Pattern to be replaced in the image names."),

        scripts.String(
            "Replacement_Pattern", grouping="4.3", optional=True, default="Project_12",
            description="Pattern to replace the matched regex pattern."),

        version="0.2",
        authors=["Jens Wendt"],
        institutions=["University of Münster"],
        contact="jens.wendt@uni-muenster.de",
    )

    try:
        # get the script parameters 
        script_params = client.getInputs(unwrap=True)
        print(f"script parameters:\n{json.dumps(script_params, indent=2)}"
              "\n######################\n")

        # wrap client to use the Blitz Gateway
        conn = BlitzGateway(client_obj=client)

        # get the correct microscope from the config
        specification =  config_json[script_params["Specification"]]

        # call the main function to add technical metadata to the images
        rename_message, image_counter = set_new_names(conn, script_params, specification)

        message = (
            f"Renamed {image_counter} images according to the {script_params['Specification']} pattern. "
            f"{rename_message}"
        )

        client.setOutput("Message", rstring(message))


    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()