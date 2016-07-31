#!/usr/bin/python
"""
The MIT License (MIT)
Copyright (c) 2016, Ruslan Zhenetl
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import os

import six
import yaml
from graphviz import Digraph
from xmltodict import unparse


class JsonAsNodeTree(object):
    """
    Json visitor implementing node tree interface

    >>> nt = JsonAsNodeTree()
    >>> nt.get_name('node')
    'node'
    >>> nt.get_children('node')
    []
    >>> nt.get_name({'node': None})
    'node'
    >>> nt.get_children({'node': None})
    []
    >>> nt.get_children({'node': 'child'})
    ['child']
    >>> nt.get_children({'node': ['child']})
    ['child']
    >>> nt.get_children({'node': {'child': None}})
    [{'child': None}]
    >>> nt.get_children({'node': ['child1', 'child2']})
    ['child1', 'child2']
    >>> nt.get_children({'node': {'child1': None, 'child2': []}})
    [{'child1': None}, {'child2': []}]
    >>> nt.get_children({'node': {'_attr': 'val', 'child': None}})
    [{'child': None}]
    >>> nt.get_attrs({'node': {'_attr': 'val', 'child': None}})
    {'attr': 'val'}
    """

    def __init__(self, attr_prefix='_'):
        self.attr_prefix = attr_prefix

    @staticmethod
    def get_name(tree):
        # type: (JsonAsNodeTree, Union[basestring, dict]) -> basestring
        if isinstance(tree, six.string_types):
            return tree
        if isinstance(tree, dict) and len(tree) == 1:
            return next(six.iterkeys(tree))
        raise ValueError('{} can\'t represent a node tree'.format(tree))

    @staticmethod
    def get_subtrees(tree):
        # type: (JsonAsNodeTree, Union[basestring, dict]) -> list
        if isinstance(tree, six.string_types):
            return []

        if isinstance(tree, dict):
            if len(tree) > 1:
                return [{k: v} for k, v in tree.items()]

            subtree = next(six.itervalues(tree))
            if subtree is None:
                return []
            if isinstance(subtree, six.string_types):
                return [subtree]
            if isinstance(subtree, list):
                return subtree
            if isinstance(subtree, dict):
                return [{k: v} for k, v in subtree.items()]

        raise ValueError('{} can\'t represent a node tree'.format(tree))

    def get_children(self, tree):
        # type: (JsonAsNodeTree, Union[basestring, dict]) -> list
        return [
            s for s in self.get_subtrees(tree)
            if not (
                isinstance(s, dict) and
                next(six.iterkeys(s)).startswith(self.attr_prefix)
            )
        ]

    def get_attrs(self, tree):
        # type: (JsonAsNodeTree, Union[basestring, dict]) -> dict
        if isinstance(tree, dict) and len(tree) == 1:
            children = next(six.itervalues(tree))
            if isinstance(children, dict):
                return {
                    k[1:]: v for k, v in children.items()
                    if k.startswith(self.attr_prefix)
                }
        return {}


nt = JsonAsNodeTree()


def group_by_namespace(attrs, namespaces):
    # type: (dict, Iterble) -> dict
    """
    >>> group_by_namespace({'test': 1, 'ns_check': 2}, ['ns_'])
    {'': {'test': 1}, 'ns_': {'check': 2}}
    """
    groups = {'': {}}

    for namespace in namespaces:
        groups[namespace] = {}
        for key, value in attrs.items():
            _, found_namespace, new_key = key.rpartition(namespace)
            groups[found_namespace][new_key] = value
    return groups


def tree_elements(tree, nodes={}, edges={}, cascade={}):
    # type: (Union[basestring, dict], dict, dict) -> Iterable, Iterable
    """
    >>> tree_elements({'parent': {'_attr': 0, 'child': None}})
    ({'parent': {'attr': 0}, 'child': {}}, {('parent', 'child'): {}})
    """
    nodes = nodes.copy()
    edges = edges.copy()
    cascade = cascade.copy()

    attrs = nt.get_attrs(tree)
    attr_groups = group_by_namespace(attrs, ('arrow_', 'cascade_'))
    cascade.update(attr_groups['cascade_'])

    children = nt.get_children(tree)
    for child in nt.get_children(tree):
        nodes, edges = tree_elements(
            tree=child, nodes=nodes, edges=edges, cascade=cascade,
        )

    try:
        name = nt.get_name(tree)
    except ValueError:
        return nodes, edges

    attrs = dict(attr_groups[''], **cascade)
    nodes.setdefault(name, {}).update(attrs)
    for child in children:
        child_name = nt.get_name(child)
        attrs = nt.get_attrs(child)
        attrs = group_by_namespace(attrs, ('arrow_',))['arrow_']
        edges.setdefault((name, child_name), {}).update(attrs)
    return nodes, edges


def tree_to_dot(tree):
    # type: (Union[basestring, dict]) -> Iterable, Iterable
    dot = Digraph()

    if 'graph' in tree:
        graph = tree['graph']

        attrs = nt.get_attrs({None: graph})
        attr_groups = group_by_namespace(attrs, ('node_',))
        dot.node_attr.update(attr_groups['node_'])
        dot.graph_attr.update(attr_groups[''])

        nodes, edges = tree_elements(graph)
        for (a, b), attrs in edges.items():
            dot.edge(b, a, **attrs)
        for node, attrs in nodes.items():
            dot.node(node, **attrs)

    if 'reverse graph' in tree:
        graph = tree['reverse graph']
        attrs = nt.get_attrs({None: graph})
        attr_groups = group_by_namespace(attrs, ('node_',))
        dot.node_attr.update(attr_groups['node_'])
        dot.graph_attr.update(attr_groups[''])

        nodes, edges = tree_elements(graph)
        for (a, b), attrs in edges.items():
            dot.edge(a, b, **attrs)
        for node, attrs in nodes.items():
            dot.node(node, **attrs)

    for name, html_tree in tree.get('html', {}).items():
        html = unparse(html_tree, full_document=False, pretty=True)
        dot.node(name, '<\n' + html + '\n>', shape='plaintext')

    for name, csv in tree.get('csv', {}).items():
        html = unparse({
            'table': {
                '@cellspacing': '0',
                'tr': [
                    {'td': line.split(',')}
                    for line in csv.strip().split('\n')
                ]
            }
        }, full_document=False, pretty=True)

        dot.node(name, '<\n' + html + '\n>', shape='plaintext')
    return dot


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'file', help='graph file to draw', type=argparse.FileType('r')
    )
    args = parser.parse_args()

    file_path, file_name = os.path.split(args.file.name)
    output_name, _, _ = file_name.partition('.yml')

    tree = yaml.load(args.file)
    dot = tree_to_dot(tree)
    dot.format = 'png'
    dot.render(os.path.join(file_path, output_name + '.dot'))
