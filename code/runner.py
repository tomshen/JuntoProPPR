#!/usr/bin/env python
import argparse
from collections import defaultdict
import io
import json
import logging
import operator
import os
import os.path as path
import re
import subprocess

import convert


JUNTO_DIR = './lib/junto'

PROPPR_DIR = './lib/ProPPR'
PROPPR_CP = '{0}/conf:{0}/bin:{0}/lib/*'.format(PROPPR_DIR)
DEFAULT_THREADS = 8

DEFAULT_MEM_SIZE = '32g'
DEFAULT_GRAPH_DIR = convert.DEFAULT_GRAPH_DIR

logger = logging.getLogger('runner')
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def run_junto(config_filename, mem_size=DEFAULT_MEM_SIZE):
    junto_env = os.environ.copy()
    junto_env['JUNTO_DIR'] = path.join(os.getcwd(), 'lib/junto')
    junto_env['PATH'] = junto_env['JUNTO_DIR'] + ':' + junto_env['PATH']
    junto_env['JAVA_MEM_FLAG'] = '-Xmx{0}'.format(mem_size)
    logger.info('Running Junto on %s', config_filename)
    subprocess.call(['{0}/bin/junto'.format(JUNTO_DIR), 'config',
        config_filename], env=junto_env)
    with open(config_filename) as config_file:
        return convert_junto_results(
            convert.parse_junto_config(config_file)['output_file'])


def convert_junto_results(output_filename):
    logger.info('Converting Junto results')
    def parse_labels(s):
        """Returns list of labels, sorted by descending score"""
        scores = s.split()
        return [label for _, label in sorted(
            [(float(scores[i+1]), scores[i])
            for i in xrange(0, len(scores), 2)], reverse=True)]

    with io.open(output_filename, 'r', encoding='utf-8') as f:
        nodes = {}
        for line in f:
            row = line.split('\t')
            name = row[0]
            sorted_labels = parse_labels(row[3])
            nodes[name] = sorted_labels
        return nodes


def run_srw(config_filename, mem_size=DEFAULT_MEM_SIZE, threads=DEFAULT_THREADS):
    data_name = path.basename(config_filename).split('.')[0]
    srw_output = path.join(DEFAULT_GRAPH_DIR, data_name + '.out.srw')
    logger.info('Running SRW on %s', data_name)
    command = ['java', '-Xmx{0}'.format(mem_size), '-cp', PROPPR_CP,
        'edu.cmu.ml.proppr.Propagator', config_filename, srw_output, str(threads)]
    logger.info('Calling: %s', ' '.join(command))
    subprocess.call(command)
    return convert_srw_results(srw_output)


def convert_srw_results(results_filename):
    logger.info('Converting SRW results')
    def load_results(results_file):
        results = {}
        with open(results_file) as results_fp:
            for line in results_fp:
                try:
                    node, labels_string = line.strip().split('\t', 1)
                    labels = labels_string.split('\t')
                    results[node] = labels
                except:
                    pass
        return results

    raw_results = load_results(results_filename)
    return raw_results


def write_results(results, output_file):
    for node, labels in results.items():
        line = node + '\t' + '\t'.join(labels) + '\n'
        output_file.write(unicode(line))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Runs Junto or SRW')
    parser.add_argument('algorithm', choices=['junto', 'srw'])
    parser.add_argument('--config', dest='junto_config',
            type=str, help='Junto config file')
    parser.add_argument('--mem', dest='mem_size', default=DEFAULT_MEM_SIZE,
        help='Java memory size')
    parser.add_argument('-o', dest='output_file', type=str,
        required=True)
    parser.add_argument('--threads', dest='threads', default=DEFAULT_THREADS,
        help='Number of threads for SRW')
    args = parser.parse_args()

    if not path.exists(DEFAULT_GRAPH_DIR):
        os.makedirs(DEFAULT_GRAPH_DIR)

    if args.algorithm == 'junto':
        results = run_junto(args.junto_config, args.mem_size)
    elif args.algorithm == 'srw':
        results = run_srw(args.junto_config, args.mem_size, args.threads)

    if args.output_file:
        with io.open(args.output_file, 'w', encoding='utf-8') as output_file:
            write_results(results, output_file)
