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
		superclass_name = api.api_obj.get("extends")
		while superclass_name is not None:
			if superclass_name == "Titanium.UI.View":
				return True
			superclass = all_annotated_apis[superclass_name]
			superclass_name = superclass.api_obj.get("extends")
	return False

def transform_one_api(api):
	transformed = create_dict_for_json(api)
	transformed["methods"] = to_json_methods(api)
	transformed["events"] = to_json_events(api)
	transformed["properties"] = to_json_properties(api)
	if "extends" in api.api_obj:
		transformed["extends"] = api.api_obj["extends"]
	else:
		transformed["extends"] = "Object"

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
	return html.replace("\n", "\\n").replace('"', '\\"').replace('href=\\"', 'href=\\"http://developer.appcelerator.com/apidoc/mobile/latest/');

def get_doc_for_object(object):
	retVal = []
	
	if "summary" in object and object["summary"] != None:
		retVal.append(object["summary"])
	
	if "deprecated" in object and object["deprecated"] != None:
		retVal.append("\n<strong>@deprecated</strong>")
	
	if "permission" in object and object["permission"] != None:
		retVal.append("\n(Permission: %s)" % object["permission"])
	
	if "description" in object and object["description"] != None:
		retVal.append('\n%s' % object["description"])
	
	#if "examples" in object and object["examples"] != None:
	#	retVal.append("\n<strong>Code Examples:</strong>")
	#	for example in object["examples"]:
	#		retVal.append("\n\n %s" % example["description"])
	#		retVal.append("\n%s" % example["code"])
	
	if "platforms" in object and object["platforms"] != None:
		retVal.append("\n\n<strong>Platform Availability:</strong><ul>")
		for platform in object["platforms"]:
			retVal.append("<li>%s since %s</li>" % (platform["pretty_name"], platform["since"]))
		retVal.append("</ul>")
	
	return clean_html_for_comment(''.join(retVal))

def get_jst_for_property(key, property, type):
	retVal = "[\n\t\t\t\t{"
	
	# guid
	retVal = '%s\n\t\t\t\t\t"guid": "ti:%s.%s[0]"' % (retVal, key, property["name"])
	
	# doc url
	docUrl = "http://docs.appcelerator.com/titanium/latest/#!/api/%s-property-%s" % (key, property["name"])
	retVal = '%s,\n\t\t\t\t\t"docUrl": "%s"' % (retVal, docUrl)
	
	# doc
	retVal = '%s,\n\t\t\t\t\t"doc": "%s"' % (retVal, get_doc_for_object(property))
	
	# self properties
	retVal = '%s,\n\t\t\t\t\t"properties": { "___proto__": [ "ti:%s.%s" ]}' % (retVal, key, type)
	
	retVal = "%s\n\t\t\t\t}\n\t\t\t]" % retVal
	return retVal

def get_jst_for_method(key, method):
	if key == "":
		indent = ''
		retVal = "{"
	else:
		indent = '\t\t\t'
		retVal = "[\n%s\t{" % indent
	
	# guid
	if key == "":
		guid = '%s' % method["name"]
	else:
		guid = '%s.%s' % (key, method["name"])
	retVal = '%s\n%s\t\t"guid": "ti:%s[0]"' % (retVal, indent, guid)
	
	# doc url
	if key == "":
		docUrl = "http://docs.appcelerator.com/titanium/latest/#!/api/Global-method-%s" % (method["name"])
	else:
		docUrl = "http://docs.appcelerator.com/titanium/latest/#!/api/%s-method-%s" % (key, method["name"])
	
	retVal = '%s,\n%s\t\t"docUrl": "%s"' % (retVal, indent, docUrl)
	
	# doc
	retVal = '%s,\n%s\t\t"doc": "%s"' % (retVal, indent, get_doc_for_object(method))
	
	# parameters
	#{'description': None, 'deprecated': None, 'filename': 'Global.L-method.key-param', 'optional': False, 'summary': u'<p>Key used to lookup the localized string.</p>', 'type': 'String', 'name': 'key'}
	#{ "id": "targetBuffer", "type": [ "es5:Object/prototype" ] }
	retVal = '%s,\n%s\t\t"fargs": [' % (retVal, indent)
	parameters = method["parameters"]
	isFirstP = True
	for parameter in parameters:
		if isFirstP:
			isFirstP = False
		else:
			retVal = '%s,' % retVal
		retVal = '%s\n%s\t\t\t{ "id": "%s", "type": [ "ti:%s" ] }' % (retVal, indent, parameter["name"], parameter["type"])
	retVal = '%s\n%s\t\t]' % (retVal, indent)
	
	# return value
	returns = method["returns"]
	if "type" not in returns:
		returns = returns[0]
	retVal = '%s,\n%s\t\t"properties": { "_return": [ "ti:%s" ]}' % (retVal, indent, returns["type"])
	
	if key == "":
		retVal = "%s\n%s\t}" % (retVal, indent)
	else:
		retVal = "%s\n%s\t}\n%s]" % (retVal, indent, indent)
	
	return retVal

def make_name_js_safe(name):
	if name == "default":
		return "def"
	return name

def convert_type_to_string(val, lenient):
	if type(val) is dict:
		val = val["type"]
	if type(val) is list:
		retVal = "("
		for v in val:
			if type(v) is dict:
				retVal = "%s%s|" % (retVal, convert_type_to_string(v["type"], lenient))
			else:
				retVal = "%s%s|" % (retVal, convert_type_to_string(v, lenient))
		return "%s)" % retVal[:-1]
	if val.find("Dictionary<") != -1:
		return "!Object"
	if val.find("Dictionary") != -1:
		return "!Object"
	if val.find("Callback<") != -1:
		return "function(%s)" % val[9:-1]
	if lenient and val.find("Titanium.") != -1:
		val = "(%s|Object)" % val
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

def dump_sub_modules(tree, keys, key):
	retVal = ""
	
	for subKey in keys:
		isChild = subKey.startswith('%s.' % key)
		subName = subKey[len(key) + 1:]
		isDirectChild = subName.find('.') == -1
		if isChild and isDirectChild:
			# comma
			if retVal != "":
				retVal = "%s," % retVal
			# key and value
			retVal = '%s\n\t\t\t"_%s": %s' % (retVal, subName, get_jst_for_property(key, tree[subKey], subName))
	
	return retVal

def get_properties_for_object(tree, keys, key, object):
	
	retVal = dump_sub_modules(tree, keys, key)
	
	if "properties" in object and object["properties"] != None:
		for property in object["properties"]:
			# comma
			if retVal != "":
				retVal = "%s," % retVal
			# key and value
			retVal = '%s\n\t\t\t"_%s": %s' % (retVal, property["name"], get_jst_for_property(key, property, property["type"]))
	
	if "methods" in object and object["methods"] != None:
		for method in object["methods"]:
			# comma
			if retVal != "":
				retVal = "%s," % retVal
			# key and value
			retVal = '%s\n\t\t\t"_%s": %s' % (retVal, method["name"], get_jst_for_method(key, method))
	
	return retVal

def dump_one(f, keys, tree, key, printKeyAs):
	# key
	f.write('\n\t"ti:%s": {' % printKeyAs)
	
	# guid
	f.write('\n\t\t"guid": "ti:%s"' % printKeyAs)
	
	# hidden (if not "Titanium" or "Global")
	if key not in ["Titanium", "Global"]:
		f.write(',\n\t\t"kind": "hidden"')
	
	# doc url
	f.write(',\n\t\t"docUrl": "http://docs.appcelerator.com/titanium/latest/#!/api/%s"' % key)
	
	# doc
	f.write(',\n\t\t"doc": "%s"' % get_doc_for_object(tree[key]))
	
	# body
	properties = get_properties_for_object(tree, keys, key, tree[key])
	if properties != "":
		f.write(',\n\t\t"properties": {%s\n\t\t}' % properties)
	
	# close
	f.write('\n\t}')

def dump(output_folder, keys, tree, f):
	if f == None:
		f = open(os.path.join(output_folder, "titanium.jst"), "w")
	f.write('{')
	isFirst = True
	
	for key in keys:
		
		# comma
		if isFirst == True:
			isFirst = False
		else:
			f.write(',')
		
		dump_one(f, keys, tree, key, key)
		if key == "Titanium":
			f.write(',')
			dump_one(f, keys, tree, key, "Ti")
	
	glob = tree["Global"]
	if "methods" in glob and glob["methods"] != None:
		for method in glob["methods"]:
			# key and value
			f.write(',\n\t"ti:%s": %s' % (method["name"], get_jst_for_method("", method)))
	
	f.write('\n}')
	f.close()

def generate(raw_apis, annotated_apis, options):
	global all_annotated_apis, log
	all_annotated_apis = annotated_apis
	log_level = TiLogger.INFO
	if options and options.verbose:
		log_level = TiLogger.TRACE
	log = TiLogger(None, level=log_level, output_stream=sys.stderr)
	log.info("Generating JST")

	# Apply HTML annotations because we make use of some of them here.
	html_generator.generate(raw_apis, annotated_apis, None)
	all_annotated_apis = html_generator.all_annotated_apis
	tree = {};
	keys = annotated_apis.keys()
	keys.sort()
	for key in keys:
		one_api = annotated_apis[key]
		# log.trace("Transforming %s to JST" % key)
		tree[key] = transform_one_api(one_api)
	if options.stdout:
		dump(None, keys, tree, sys.stdout)
	else:
		# Output to a file named api-jst.js either in the folder
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
