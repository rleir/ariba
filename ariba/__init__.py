from pkg_resources import get_distribution

try:
    __version__ = get_distribution('ariba').version
except:
    __version__ = 'local'


__all__ = [
    'aln_to_metadata',
    'assembly',
    'assembly_compare',
    'assembly_variants',
    'bam_parse',
    'best_seq_chooser',
    'card_record',
    'cdhit',
    'cluster',
    'clusters',
    'common',
    'external_progs',
    'faidx',
    'flag',
    'histogram',
    'link',
    'mapping',
    'read_store',
    'reference_data',
    'ref_genes_getter',
    'ref_preparer',
    'report',
    'report_filter',
    'scaffold_graph',
    'samtools_variants',
    'sequence_metadata',
    'sequence_variant',
    'summary',
    'summary_cluster',
    'summary_sample',
    'tasks',
    'versions',
    'vfdb_parser',
]

from ariba import *
