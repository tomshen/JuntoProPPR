#!/usr/bin/env python
import argparse
from collections import Counter
import json
import logging
import os
import os.path as path
import random


DEFAULT_GRAPH_DIR = './graph'
logger = logging.getLogger('convert')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def ground_graph(graph_edges, seeds, labels):
    def fresh_gen():
        label = [0]
        def fresh():
            label[0] += 1
            return label[0]
        return fresh

    logger.info('Starting grounding')

    graphs = []
    edges = []
    nodes = {}
    node_doc = {}
    fresh = fresh_gen()

    features = [
        'seed',
        'assoc',
        'id(trueLoop)',
        'id(trueLoopRestart)',
        'fixedWeight',
        'id(restart)',
        'id(alphaBooster)'
    ] # 1-indexed

    for node1, node2, weight in graph_edges:
        if node1 not in nodes:
            nodes[node1] = fresh()
            node_doc[nodes[node1]] = node1
        if node2 not in nodes:
            nodes[node2] = fresh()
            node_doc[nodes[node2]] = node2
        n1 = nodes[node1]
        n2 = nodes[node2]
        edges.append((n1, n2, [2]))
        edges.append((n2, n1, [2]))

    start_node = fresh()

    for label in labels:
        seed_edges = []
        for node in nodes:
            if node in seeds and seeds[node] == label:
                seed_edges.append((start_node, nodes[node], [1]))

        query = label # 'assoc({0},X-1)  #v:[?].'.format(label)
        graphs.append({
            'query': query,
            'pos_nodes': [start_node],
            'neg_nodes': [],
            'node_count': len(nodes),
            'edges': seed_edges + edges,
            'features': list(features),
            'node_doc': node_doc
        })
    logger.info('Finished grounding')
    return graphs


def add_degree_feature(graph):
    in_deg = Counter()
    out_deg = Counter()
    for u, v, _ in graph['edges']:
        out_deg[u] += 1
        in_deg[v] += 1
    in_feat_map = {}
    out_feat_map = {}
    for u, d in in_deg.items():
        graph['features'].append('inDeg({0},{1})'.format(u, d))
        in_feat_map[u] = len(graph['features'])
    for u, d in out_deg.items():
        graph['features'].append('outDeg({0},{1})'.format(u, d))
        out_feat_map[u] = len(graph['features'])
    new_edges = []
    for u, v, f in graph['edges']:
        f.append(in_feat_map[v])
        f.append(out_feat_map[u])
    return graph


def parse_junto_config(config_file):
    logger.info('Parsing Junto config file %s', config_file.name)
    config = dict()
    for line in config_file:
        try:
            key, value = line.strip().split(' = ')
            config[key] = value
        except:
            continue
    return config


def parse_junto_graph(graph_file):
    logger.info('Parsing Junto graph file %s', graph_file.name)
    edges = []
    for line in graph_file:
        try:
            node1, node2, weight = line.split()
            edges.append((node1, node2, weight))
        except ValueError:
            logger.error('Error parsing edge: %s', line)
    return edges


def parse_junto(config_file):
    config = parse_junto_config(config_file)
    edges = parse_junto_graph(open(config['graph_file']))
    seeds = dict((node, label) for node, label, weight in
        parse_junto_graph(open(config['seed_file'])))
    return edges, seeds


def convert_junto_to_proppr(junto_config_file, graph_dir, sample_percent=100):
    name = path.basename(junto_config_file.name).split('.')[0]

    junto_edges, seeds = parse_junto(junto_config_file)
    junto_edges = random.sample(junto_edges,
        int(len(junto_edges) * sample_percent / 100))
    labels = set(seeds.itervalues())
    grounded_graph = ground_graph(junto_edges, seeds, labels)

    logger.info('Converting grounded graphs to strings')
    grounded_strings = ('\t'.join([
        proppr_query['query'],
        ','.join(['1']), # query_vec
        ','.join(str(i) for i in proppr_query['pos_nodes']),
        ','.join(str(i) for i in proppr_query['neg_nodes']),
        str(proppr_query['node_count']),
        str(len(proppr_query['edges'])),
        ':'.join(proppr_query['features']),
        '\t'.join('{0}->{1}:{2}'.format(n1, n2, ','.join(str(i) for i in f))
            for n1, n2, f in proppr_query['edges'])
    ]) + '\n' for proppr_query in grounded_graph)

    logger.info('Writing grounded graphs')
    with open(path.join(graph_dir, name + '.grounded'), 'w') as grounded_fp:
        for s in grounded_strings:
            grounded_fp.write(s)

    logger.info('Writing node mapping')
    node_map = grounded_graph[0]['node_doc'] # FIXME: this is hacky
    with open(path.join(graph_dir, name + '.map'), 'w') as node_map_fp:
        json.dump(node_map, node_map_fp)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Convert Junto graphs to ProPPR SRW graphs.')
    parser.add_argument('junto_config', type=file, help='Junto config file')
    parser.add_argument('-p', dest='sample_percent', type=int, default=100,
        help='Percent of Junto graph edges to use in the SRW graph')
    parser.add_argument('-d', dest='graph_dir', type=str,
        default=DEFAULT_GRAPH_DIR, help='Directory to write SRW graphs to')
    args = parser.parse_args()

    if not path.exists(args.graph_dir):
        os.makedirs(args.graph_dir)

    convert_junto_to_proppr(args.junto_config, args.graph_dir,
        args.sample_percent)
    args.junto_config.close()
