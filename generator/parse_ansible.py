#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import __main__
import json
import os
from types import SimpleNamespace

ansible_available = False
try:
    import ansible
    ansible_available = True
except:
    pass

if ansible_available:
    from ansible.cli.doc import DocCLI
    from ansible.playbook import Play
    from ansible.playbook.block import Block
    from ansible.playbook.role import Role
    from ansible.playbook.task import Task
    from ansible.utils.display import Display

    try:
        from ansible.plugins.loader import lookup_loader, module_loader
        from ansible.utils import plugin_docs
        use_old_loader = False
        BLACKLIST_MODULES = plugin_docs.BLACKLIST['MODULE']
    except ImportError:
        from ansible.plugins import lookup_loader, module_loader
        from ansible.utils import module_docs as plugin_docs
        use_old_loader = True
        BLACKLIST_MODULES = plugin_docs.BLACKLIST_MODULES

    try:
        from ansible.plugins.loader import fragment_loader
        USE_FRAGMENT_LOADER = True
    except ImportError:
        fragment_loader = None
        USE_FRAGMENT_LOADER = False

    __main__.display = Display()
    doc_cli = DocCLI(['ansible atom'])


def get_module_list():
    module_paths = module_loader._get_paths()
    for path in module_paths:
        if use_old_loader:
            doc_cli.find_modules(path)
        else:
            try:
                founds = doc_cli.find_plugins(path, 'module')
            except TypeError:
                founds = doc_cli.find_plugins(path, 'plugins', 'module')
            if founds:
                doc_cli.plugin_list.update(founds)
    module_list = (
        doc_cli.module_list if use_old_loader else doc_cli.plugin_list)
    return sorted(set(module_list))


def main():
    module_keys = ('module', 'short_description', 'options', 'deprecated')
    result = {'modules': [], 'directives': {}, 'lookup_plugins': []}

    for module in get_module_list():
        if module in BLACKLIST_MODULES:
            continue
        filename = module_loader.find_plugin(module, mod_type='.py')
        if filename is None:
            continue
        if filename.endswith(".ps1"):
            continue
        if os.path.isdir(filename):
            continue
        get_docstring_args = ((filename, fragment_loader)
                              if USE_FRAGMENT_LOADER else (filename,))
        try:
            doc = plugin_docs.get_docstring(*get_docstring_args)[0]
            filtered_doc = {key: doc.get(key, None) for key in module_keys}
            result['modules'].append(filtered_doc)
        except Exception as e:
            pass

    for aclass in (Play, Role, Block, Task):
        aobj = aclass()
        name = type(aobj).__name__

        for attr in aobj.__dict__['_attributes']:
            if 'private' in attr and attr.private:
                continue
            direct_target = result['directives'].setdefault(attr, [])
            direct_target.append(name)
            if attr == 'action':
                local_action = result['directives'].setdefault(
                    'local_action', [])
                local_action.append(name)
    result['directives']['with_'] = ['Task']

    for lookup in lookup_loader.all(path_only=True):
        name = os.path.splitext(os.path.basename(lookup))[0]
        result['lookup_plugins'].append(name)

    return json.dumps(result)

def generate_codesnippets(json_data, use_file=False):
    if use_file:
        with open(json_data) as f:
            json_data = f.read()
    
    obj = json.loads(json_data, object_hook=lambda d: SimpleNamespace(**d))
    # obj = json.loads(json_data)

    class Snippet(object):
        prefix = ""
        body = []
        description = ""
    
    class SnippetEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, Snippet):
                return obj.__dict__
            # Let the base class default method raise the TypeError
            return json.JSONEncoder.default(self, obj)

    def escape_tmsyntax(value):
        val = value
        if "\\" in val:
            val = val.replace("\\","\\\\")
        if "}" in val:
            val = val.replace("}","\\}")
        if "$" in val:
            val = val.replace("$","\\$")
        return val

    snippet_result = {}
    snippet_current = None
    for module in obj.modules:
        print(module.module)
        # print(dir(module.options))
        snippet_current = Snippet()
        snippet_current.prefix = module.module + "_snippet"
        snippet_current.description = module.short_description
        snippet_current.body = [module.module + ":"]

        mod_options = None
        test = {}
        if module.options:
            # print(repr(module.options))
            # print(repr(module.options.__dict__))
            # test.
            option_names = list(module.options.__dict__.keys())
            sorted_option_names = sorted(option_names, key=lambda x: getattr(getattr(module.options, x), "required", False), reverse=True)

            for i, mod in enumerate(sorted_option_names):
                # print(mod)
                option = getattr(module.options, mod)
                is_required = hasattr(option, "required") and option.required
                is_required_text = 'required' if is_required else 'not required'
                has_choices = hasattr(option, "choices")
                choices = None

                if mod and mod != "":
                    line = "  " + mod + ": "

                    if has_choices:
                        choices = [str(x) for x in option.choices]
                        line += '${' + str(i + 1) + '|' + ','.join(choices) + '|}'
                    elif hasattr(option, "default"):
                        val = str(option.default)
                        val = escape_tmsyntax(val)
                        if " " in val:
                            val = '"{}"'.format(val)
                        
                        line += '${' + str(i + 1) + ':' + val + '}'
                    else:
                        #line += '${' + str(i + 1) + ':' + '}' # use getattr with default above as alternative
                        line += '$' + str(i + 1) # use getattr with default above as alternative
                    
                    line += ' # ' + is_required_text + '.'

                    if has_choices:
                        line += ' choices: ' + ';'.join(choices) + '.'

                    line += ' ' + escape_tmsyntax(" ".join(option.description))

                    snippet_current.body.append(line)

        snippet_result["ansible_" + module.module] = snippet_current

    return json.dumps(snippet_result, cls=SnippetEncoder, indent="\t")

if __name__ == '__main__':
    #print(main())
    if ansible_available:
        d = generate_codesnippets(main(), use_file=False)
    else:
        d = generate_codesnippets("ansible.json", use_file=True)
    with open("ansible_codesnippets.json", "w") as f:
        f.write(d)
