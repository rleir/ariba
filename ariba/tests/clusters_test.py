import unittest
import shutil
import os
import pickle
import pysam
import pyfastaq
import filecmp
from ariba import clusters, external_progs, reference_data, sequence_metadata

modules_dir = os.path.dirname(os.path.abspath(clusters.__file__))
data_dir = os.path.join(modules_dir, 'tests', 'data')
extern_progs = external_progs.ExternalProgs()


def file_to_list(infile):
    f = pyfastaq.utils.open_file_read(infile)
    lines = [x for x in f.readlines()]
    pyfastaq.utils.close(f)
    return lines


class TestClusters(unittest.TestCase):
    def setUp(self):
        self.cluster_dir = 'tmp.Cluster'
        self.refdata_dir = 'tmp.RefData'
        os.mkdir(self.refdata_dir)
        shutil.copyfile(os.path.join(data_dir, 'clusters_test_dummy_db.fa'), os.path.join(self.refdata_dir, 'refcheck.01.check_variants.non_coding.fa'))
        with open(os.path.join(self.refdata_dir, 'info.txt'), 'w') as f:
            print('genetic_code\t11', file=f)

        with open(os.path.join(self.refdata_dir, 'cdhit.clusters.pickle'), 'wb') as f:
            pickle.dump({'x': {'x'}}, f)

        reads1 = os.path.join(data_dir, 'clusters_test_dummy_reads_1.fq')
        reads2 = os.path.join(data_dir, 'clusters_test_dummy_reads_2.fq')
        self.clusters = clusters.Clusters(self.refdata_dir, reads1, reads2, self.cluster_dir, extern_progs, clean=False)


    def tearDown(self):
        shutil.rmtree(self.cluster_dir)
        shutil.rmtree(self.refdata_dir)


    def test_load_reference_data_info_file(self):
        '''test _load_reference_data_info_file'''
        infile = os.path.join(data_dir, 'clusters_test_load_data_info_file')
        expected = {'genetic_code': 11}
        got = clusters.Clusters._load_reference_data_info_file(infile)
        self.assertEqual(expected, got)


    def test_load_reference_data_from_dir(self):
        '''test _load_reference_data_from_dir'''
        indir = os.path.join(data_dir, 'clusters_test_load_reference_data_from_dir')
        got_refdata, got_clusters = clusters.Clusters._load_reference_data_from_dir(indir)
        expected_seq_dicts = {
            'variants_only': {'variants_only1': pyfastaq.sequences.Fasta('variants_only1', 'atggcgtgcgatgaataa')},
            'presence_absence': {'presabs1': pyfastaq.sequences.Fasta('presabs1', 'atgatgatgagcccggcgatggaaggcggctag')},
            'non_coding': {'noncoding1': pyfastaq.sequences.Fasta('noncoding1', 'ACGTA')},
        }
        self.assertEqual(expected_seq_dicts, got_refdata.seq_dicts)
        self.assertEqual(11, got_refdata.genetic_code)

        expected_metadata = {
            'presabs1': {
                '.': {sequence_metadata.SequenceMetadata('presabs1\t.\t.\t.\tpresabs1 description')},
                'n': {},
                'p': {}
            },
            'variants_only1': {
                '.': set(),
                'n': {},
                'p': {1: {sequence_metadata.SequenceMetadata('variants_only1\tp\tC2I\t.\tdescription of variants_only1 C2I')}}
            }
        }
        self.assertEqual(expected_metadata, got_refdata.metadata)

        expected_clusters = {'key1': 1, 'key2': 2}
        self.assertEqual(expected_clusters, got_clusters)


    def test_bam_to_clusters_reads_no_reads_map(self):
        '''test _bam_to_clusters_reads when no reads map'''
        clusters_dir = 'tmp.Cluster.test_bam_to_clusters_reads_no_reads_map'
        reads1 = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads_no_reads_map_1.fq')
        reads2 = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads_no_reads_map_2.fq')
        ref = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.db.fa')
        refdata = reference_data.ReferenceData(presence_absence_fa = ref)
        c = clusters.Clusters(self.refdata_dir, reads1, reads2, clusters_dir, extern_progs, clean=False)
        shutil.copyfile(os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads_no_reads_map.bam'), c.bam)
        c._bam_to_clusters_reads()

        self.assertEqual({}, c.insert_hist.bins)
        self.assertEqual({}, c.cluster_read_counts)
        self.assertEqual({}, c.cluster_base_counts)
        self.assertEqual(0, c.proper_pairs)

        shutil.rmtree(clusters_dir)


    def test_bam_to_clusters_reads(self):
        '''test _bam_to_clusters_reads'''
        clusters_dir = 'tmp.Cluster.test_bam_to_clusters_reads'
        reads1 = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.reads_1.fq')
        reads2 = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.reads_2.fq')
        ref = os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.db.fa')
        refdata = reference_data.ReferenceData(presence_absence_fa = ref)
        c = clusters.Clusters(self.refdata_dir, reads1, reads2, clusters_dir, extern_progs, clean=False)
        shutil.copyfile(os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.bam'), c.bam)
        c._bam_to_clusters_reads()
        expected = [
            os.path.join(data_dir, 'clusters_test_bam_to_clusters.out.ref1.reads_1.fq'),
            os.path.join(data_dir, 'clusters_test_bam_to_clusters.out.ref1.reads_2.fq'),
            os.path.join(data_dir, 'clusters_test_bam_to_clusters.out.ref2.reads_1.fq'),
            os.path.join(data_dir, 'clusters_test_bam_to_clusters.out.ref2.reads_2.fq'),
        ]

        got_reads_store_lines = file_to_list(os.path.join(clusters_dir, 'read_store.gz'))
        expected_reads_store_lines = file_to_list(os.path.join(data_dir, 'clusters_test_bam_to_clusters_reads.read_store.gz'))

        self.assertEqual(expected_reads_store_lines, got_reads_store_lines)
        self.assertEqual({780:1}, c.insert_hist.bins)
        self.assertEqual({'ref1': 4, 'ref2': 2}, c.cluster_read_counts)
        self.assertEqual({'ref1': 240, 'ref2': 120}, c.cluster_base_counts)
        self.assertEqual(1, c.proper_pairs)

        shutil.rmtree(clusters_dir)


    def test_set_insert_size_data(self):
        '''test _set_insert_size_data'''
        self.clusters.insert_hist.bins = {
            1: 1,
            2: 1,
            3: 3,
            4: 3,
            5: 5,
            6: 3,
            7: 2,
            8: 2,
            9: 1,
            10: 1,
        }
        self.clusters.insert_hist.bin_width=1

        self.clusters._set_insert_size_data()
        self.assertEqual(self.clusters.insert_size, 5.5)
        self.assertEqual(self.clusters.insert_sspace_sd, 0.91)


    def test_write_reports(self):
        class FakeCluster:
            def __init__(self, lines):
                self.report_lines = lines

        clusters_dict = {
            'gene1': FakeCluster(['gene1\tline1']),
            'gene2': FakeCluster(['gene2\tline2'])
        }

        tmp_tsv = 'tmp.test_write_reports.tsv'
        tmp_xls = 'tmp.test_write_reports.xls'
        clusters.Clusters._write_reports(clusters_dict, tmp_tsv, tmp_xls)

        expected = os.path.join(data_dir, 'clusters_test_write_report.tsv')
        self.assertTrue(filecmp.cmp(expected, tmp_tsv, shallow=False))
        self.assertTrue(os.path.exists(tmp_xls))
        os.unlink(tmp_tsv)
        os.unlink(tmp_xls)


    def test_write_catted_assembled_seqs_fasta(self):
        '''test _write_catted_assembled_seqs_fasta'''
        seq1 = pyfastaq.sequences.Fasta('seq1', 'ACGT')
        seq2 = pyfastaq.sequences.Fasta('seq2', 'TTTT')
        seq3 = pyfastaq.sequences.Fasta('seq3', 'AAAA')
        class FakeAssemblyCompare:
            def __init__(self, assembled_seqs):
                if assembled_seqs is not None:
                    self.assembled_reference_sequences = {x.id: x for x in assembled_seqs}

        class FakeCluster:
            def __init__(self, assembled_seqs):
                self.assembly_compare = FakeAssemblyCompare(assembled_seqs)

        self.clusters.clusters = {
            'gene1': FakeCluster([seq1, seq2]),
            'gene2': FakeCluster([seq3]),
            'gene3': FakeCluster(None),
        }

        tmp_file = 'tmp.test_write_catted_assembled_seqs_fasta.fa'
        self.clusters._write_catted_assembled_seqs_fasta(tmp_file)
        expected = os.path.join(data_dir, 'clusters_test_write_catted_assembled_genes_fasta.expected.out.fa')
        self.assertTrue(filecmp.cmp(expected, tmp_file, shallow=False))
        os.unlink(tmp_file)


    def test_write_catted_genes_matching_refs_fasta(self):
        '''test _write_catted_genes_matching_refs_fasta'''
        seq1 = pyfastaq.sequences.Fasta('seq1', 'ACGT')
        seq3 = pyfastaq.sequences.Fasta('seq3', 'AAAA')
        class FakeAssemblyCompare:
            def __init__(self, seq, seq_type, start, end):
                self.gene_matching_ref = seq
                self.gene_matching_ref_type = seq_type
                self.gene_start_bases_added = start
                self.gene_end_bases_added = end

        class FakeCluster:
            def __init__(self, seq, seq_type, start, end):
                self.assembly_compare = FakeAssemblyCompare(seq, seq_type, start, end)

        self.clusters.clusters = {
            'gene1': FakeCluster(seq1, 'TYPE1', 1, 3),
            'gene2': FakeCluster(None, None, None, None),
            'gene3': FakeCluster(seq3, 'TYPE3', 4, 5),
        }

        tmp_file = 'tmp.test_write_catted_genes_matching_refs_fasta.fa'
        self.clusters._write_catted_genes_matching_refs_fasta(tmp_file)
        expected = os.path.join(data_dir, 'clusters_test_write_catted_genes_matching_refs_fasta.expected.out.fa')
        self.assertTrue(filecmp.cmp(expected, tmp_file, shallow=False))
        os.unlink(tmp_file)

