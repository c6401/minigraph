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

import yaml
from graphviz import Digraph
from types import MappingProxyType as FrozenDict
from typing import NamedTuple, Any, Iterable


class Edge(NamedTuple):
    parent: str
    child: Any
    parent_opts: dict = FrozenDict({})
    edge_opts: dict = FrozenDict({})

        
class Node(NamedTuple):
    name: str
    children: Iterable
    opts: dict = FrozenDict({})
    edge_opts: dict = FrozenDict({})


def graph_and_options(graph):
    if not isinstance(graph, dict):
        return graph, {}, {}
    new_graph, opts, edge_opts = graph.copy(), {}, {}
    for k, v in graph.items():
        if k.startswith('_edge_'):
            edge_opts[k[6:]] = new_graph.pop(k)
        elif k.startswith('_'):
            opts[k[1:]] = new_graph.pop(k)
    return new_graph, opts, edge_opts


def translate_dict(graph):
    for name, descendants in graph.items():
        descendants, opts, edge_opts = graph_and_options(descendants)
        children = translate(descendants)
        yield Node(name, children, opts, edge_opts)


def translate_list(graph):
    for item in graph:
        yield from translate(item)


def translate_str(name):
    yield Node(name, [])


def translate(graph):
    if isinstance(graph, dict):
        yield from translate_dict(graph)
    if isinstance(graph, list):
        yield from translate_list(graph)
    elif isinstance(graph, str):
        yield from translate_str(graph)


def nodes_to_edges(graph):
    for node in graph:
        have_children = False
        yield Edge(node.name, None, node.opts)
        for child in node.children:
            have_children = True
            yield Edge(node.name, child.name, node.opts, child.edge_opts)
            yield from nodes_to_edges([child])
        

def graph_to_dot(schema):
    dot = Digraph()
    graph = schema.get('graph')
    for edge in nodes_to_edges(translate(graph)):
        dot.node(edge.parent, **edge.parent_opts)
        if edge.child:
            dot.edge(edge.child, edge.parent, **edge.edge_opts)

    graph = schema.get('reverse graph')
    for edge in nodes_to_edges(translate(graph)):

        dot.node(edge.parent, **edge.parent_opts)
        if edge.child:
            dot.edge(edge.parent, edge.child, **edge.edge_opts)

    for name, csv in schema.get('csv', {}).items():
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
    dot = graph_to_dot(tree)
    dot.format = 'png'
    dot.render(os.path.join(file_path, output_name + '.dot'))
