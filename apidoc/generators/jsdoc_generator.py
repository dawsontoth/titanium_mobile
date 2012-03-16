#!/usr/bin/env python
#
# Copyright (c) 2011-2012 Appcelerator, Inc. All Rights Reserved.
# Licensed under the Apache Public License (version 2)

import sys, json, os

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(this_dir, "..")))
from common import dict_has_non_empty_member

# Contains TiLogger:
android_support_dir = os.path.abspath(os.path.join(this_dir, "..", "..", "support", "android"))
sys.path.append(android_support_dir)
from tilogger import *


# We piggy-back on some of the functionality from the html generator, because
# this json format includes a property named "filename" which is corresponds to
# the filename generated for the html format.
import html_generator
from html_generator import markdown_to_html

all_annotated_apis = None
log = None

def copy_key_val(source, target, key):
	if key in source:
		target[key] = source[key]

def create_dict_for_json(api):
	result = {
			"name": api.name,
			"summary": api.summary_html,
			"description": None if not api.description_html else api.description_html,
			}

	if hasattr(api, "filename_html"):
		result["filename"] = api.filename_html

	if api.typestr in ["method", "module", "proxy"]:
		result["examples"] = to_json_examples(api)

	if api.typestr == "property" and api.parent and api.parent.typestr != "event":
		result["examples"] = to_json_examples(api)

	if api.typestr in ["method", "module", "proxy", "event"]:
		result["platforms"] = api.platforms

	if api.typestr == "property" and api.parent and api.parent.typestr != "event":
		result["platforms"] = api.platforms

	if hasattr(api, "deprecated"):
		result["deprecated"] = api.deprecated

	copy_key_val(api.api_obj, result, "optional")
	copy_key_val(api.api_obj, result, "type")

	return result

def to_json_example(example):
	return {
			"description": example["title"],
			"code": markdown_to_html(example["example"])
			}

def to_json_examples(api):
	if dict_has_non_empty_member(api.api_obj, "examples"):
		return [to_json_example(e) for e in api.api_obj["examples"]]
	else:
		return []

def to_json_event_property(p):
	return create_dict_for_json(p)

def to_json_event_properties(properties):
	if not properties:
		return []
	else:
		return [to_json_event_property(p) for p in properties]

def to_json_event(event):
	result = create_dict_for_json(event)
	result["properties"] = to_json_event_properties(event.properties)
	return result

def to_json_events(api):
	if not api.events:
		return []
	return [to_json_event(event) for event in api.events]

def to_json_parameter(parameter):
	result = create_dict_for_json(parameter)
	result["optional"] = True if parameter.optional else False
	return result

def to_json_parameters(parameters):
	if not parameters:
		return []
	else:
		return [to_json_parameter(parameter) for parameter in parameters]

def to_json_method(m):
	result = create_dict_for_json(m)
	result["parameters"] = to_json_parameters(m.parameters)
	result["returns"] = m.api_obj["returns"] if "returns" in m.api_obj else {"type": "void"}
	return result

def to_json_methods(api):
	if not api.methods:
		return []
	return [to_json_method(m) for m in api.methods]

def to_json_property(p):
	result = create_dict_for_json(p)
	copy_key_val(p.api_obj, result, "permission")
	copy_key_val(p.api_obj, result, "value")
	copy_key_val(p.api_obj, result, "availability")
	copy_key_val(p.api_obj, result, "default")
	return result

def to_json_properties(api):
	if not api.properties:
		return []
	return [to_json_property(p) for p in api.properties]

def find_proxy_names_in_module(module):
	return [proxy.name for proxy in all_annotated_apis.values() if proxy.typestr == "proxy" and proxy.parent is module]

def is_view_proxy(api):
	if api.typestr != "proxy":
		return
	if api.name == "Titanium.UI.View":
		return True
	else:
		parent = api.parent
		while parent is not None:
			if parent.name == "Titanium.UI.View":
				return True
			parent = parent.parent
	return False

def transform_one_api(api):
	transformed = create_dict_for_json(api)
	transformed["methods"] = to_json_methods(api)
	transformed["events"] = to_json_events(api)
	transformed["properties"] = to_json_properties(api)

	if api.typestr == "module":
		transformed["objects"] = find_proxy_names_in_module(api)
		transformed["type"] = "module"
		transformed["subtype"] = None
	elif api.typestr == "proxy":
		transformed["type"] = "object"
		if is_view_proxy(api):
			transformed["subtype"] = "view"
		else:
			transformed["subtype"] = "proxy"
	else:
		transformed["type"] = "object"
		transformed["subtype"] = None
	return transformed

def clean_html_for_comment(html):
	return html.replace("\n", "\n * ").replace("href=\"Titanium","href=\"http://developer.appcelerator.com/apidoc/mobile/latest/Titanium");

def get_jsdoc_for_object(original, object):
	retVal = ""
	if "summary" in object and object["summary"] != None:
		retVal = "%s\n * %s" % (retVal, clean_html_for_comment(object["summary"]))
	if "permission" in object and object["permission"] != None:
		retVal = "%s\n * (Permission: %s)" % (retVal, object["permission"])
	if "description" in object and object["description"] != None:
		retVal = "%s\n * %s" % (retVal, clean_html_for_comment(object["description"]))
	
	if "examples" in object and object["examples"] != None:
		retVal = "%s\n * <b>Code Examples:</b><ul>" % (retVal)
		for example in object["examples"]:
			retVal = "%s\n * \n * %s" % (retVal, clean_html_for_comment(example["description"]))
			retVal = "%s\n * <code>%s</code>" % (retVal, example["code"].replace("\n", "\n * ").replace("/*", "\\/*").replace("*/", "*\\/"))
	
	if "platforms" in object and object["platforms"] != None:
		retVal = "%s\n * <b>Platform Availability:</b><ul>" % (retVal)
		for platform in object["platforms"]:
			retVal = "%s\n * <li>%s since %s</li>" % (retVal, platform["pretty_name"], platform["since"])
		retVal = "%s\n * </ul>" % (retVal)
	
	if "deprecated" in object and object["deprecated"] != None:
		retVal = "%s\n * @deprecated" % (retVal)
	
	if "type" in object:
		if object["type"] == "module":
			retVal = "%s\n * @interface" % (retVal)
		else:
			retVal = "%s\n * @type {%s}" % (retVal, convert_type_to_string(object))
	
	if "subtype" in object and object["subtype"] != None:
		retVal = "%s\n * @extends Titanium.%s%s" % (retVal, object["subtype"][0].capitalize(), object["subtype"][1:])
	
	if "parameters" in object and object["parameters"] != None:
		for parameter in object["parameters"]:
			type = convert_type_to_string(parameter)
			optional = ""
			if parameter["optional"]:
				optional = "="
			retVal = "%s\n * @param {%s%s} %s\t%s" % (retVal, type, optional, parameter["name"], parameter["summary"])
	
	if "returns" in object and object["returns"] != None:
		retVal = "%s\n * @return {%s}" % (retVal, convert_type_to_string(object["returns"]))
	
	return "%s\n/**\n *%s\n */" % (original, retVal)

def convert_type_to_string(val):
	if type(val) is dict:
		val = val["type"]
	if type(val) is list:
		retVal = "{("
		for v in val:
			if type(v) is dict:
				retVal = "%s%s|" % (retVal, convert_type_to_string(v["type"]))
			else:
				retVal = "%s%s|" % (retVal, convert_type_to_string(v))
		return "%s)}" % retVal[:-1]
	if val.find("Dictionary<") != -1:
		return "!Object"
	if val.find("Callback<") != -1:
		log.info("PARSED: function(%s)" % val[9:-1])
		return "function(%s)" % val[9:-1]
	return val.replace("<", ".<")

def get_def_value_for_type(type):
	if type == None:
		return type
	if type == "Number":
		return "0"
	elif type == "String":
		return "''"
	elif type == "Date":
		return "new Date()"
	elif type == "Boolean":
		return "true"
	elif type == "Object":
		return "{}"
	elif type == "Dictionary":
		return "{}"
	elif type == "Point":
		return "{ x: 0, y: 0 }"
	elif hasattr(type, "find"):
		if type.find("Array<") != -1:
			return "[]"
		elif type.find("Callback<") != -1:
			return "/** @extends %s */ function() { }" % type.replace("Callback<","").replace(">","")
	return type

def get_properties_for_object(object):
	retVal = " "
	
	if "properties" in object and object["properties"] != None:
		for property in object["properties"]:
			retVal = get_jsdoc_for_object(retVal, property)
			retVal = "%s\n\t'%s': %s," % (retVal, property["name"], get_def_value_for_type(property["type"]))
	
	if "methods" in object and object["methods"] != None:
		for method in object["methods"]:
			retVal = get_jsdoc_for_object(retVal, method)
			args = ""
			if "parameters" in method and method["parameters"]:
				for parameter in method["parameters"]:
					args = "%s%s," % (args, parameter["name"])
				args = args[:-1]
			retVal = "%s\n\t'%s': function(%s) { }," % (retVal, method["name"], args)
	
	return retVal[:-1]

def dump(output_folder, keys, tree, f):
	for key in keys:
		var = key;
		
		# Handle the special case caused by 2D and 3D matrix (properties cannot begin numerically in JS)
		if key.find(".2") != -1:
			var = "%s']" % key.replace(".2", "['2")
		elif key.find(".3") != -1:
			var = "%s']" % key.replace(".3", "['3")
		elif key == "Titanium":
			var = "Titanium = Ti"
		
		if var.find(".") == -1:
			var = "var %s" % var
		
		output = "%s\n%s = {\n%s\n};\n" % (get_jsdoc_for_object("", tree[key]), var, get_properties_for_object(tree[key]))
		if f == None:
			output_file = os.path.join(output_folder, "%s-jsdoc.js" % key)
			fi = open(output_file, "w")
			fi.write(output)
			fi.close()
		else:
			f.write(output)

def generate(raw_apis, annotated_apis, options):
	global all_annotated_apis, log
	all_annotated_apis = annotated_apis
	log_level = TiLogger.TRACE
	log = TiLogger(None, level=log_level, output_stream=sys.stderr)
	log.info("Generating JSDOC")

	# Apply HTML annotations because we make use of some of them here.
	html_generator.generate(raw_apis, annotated_apis, None)
	all_annotated_apis = html_generator.all_annotated_apis
	tree = {};
	keys = annotated_apis.keys()
	keys.sort()
	for key in keys:
		one_api = annotated_apis[key]
		# log.trace("Transforming %s to JSDOC" % key)
		tree[key] = transform_one_api(one_api)
	if options.stdout:
		dump(None, keys, tree, sys.stdout)
	else:
		# Output to a file named api-jsdoc.js either in the folder
		# specified by options.output or, if that's None, our
		# standard dist/apidoc location where we also dump
		# html output
		output_folder = None
		if options is not None and options.output:
			output_folder = options.output
		if not output_folder:
			dist_path = os.path.abspath(os.path.join(this_dir, "..", "..", "dist"))
			if os.path.exists(dist_path):
				output_folder = os.path.join(dist_path, "apidoc")
				if not os.path.exists(output_folder):
					os.mkdir(output_folder)

		if not output_folder:
			log.warn("No output folder specified and dist path does not exist.  Forcing output to stdout.")
			dump(None, keys, tree, sys.stdout)
		else:
			dump(output_folder, keys, tree, None)
