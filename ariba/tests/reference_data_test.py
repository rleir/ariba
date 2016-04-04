import unittest
import filecmp
import os
import pyfastaq
from ariba import reference_data, sequence_metadata

modules_dir = os.path.dirname(os.path.abspath(reference_data.__file__))
data_dir = os.path.join(modules_dir, 'tests', 'data')


class TestReferenceData(unittest.TestCase):
    def test_init_fails(self):
        '''Test __init__ fails when it should'''

        with self.assertRaises(reference_data.Error):
            ref_data = reference_data.ReferenceData()

        presence_absence_bad  = os.path.join(data_dir, 'reference_data_init_presence_absence_bad.fa')

        with self.assertRaises(reference_data.Error):
            ref_data = reference_data.ReferenceData(presence_absence_fa=presence_absence_bad)

        empty_fasta = os.path.join(data_dir, 'reference_data_init_empty.fa')

        with self.assertRaises(reference_data.Error):
            ref_data = reference_data.ReferenceData(presence_absence_fa=empty_fasta)


    def test_init_ok(self):
        '''Test init with good input'''
        tsv_file = os.path.join(data_dir, 'reference_data_init.tsv')
        presence_absence_fa = os.path.join(data_dir, 'reference_data_init_presence_absence.fa')
        meta1 = sequence_metadata.SequenceMetadata('gene1\tn\tA42G\tN\tfree text')
        meta2 = sequence_metadata.SequenceMetadata('gene1\tn\tA42T\tN\tfree text2')
        meta3 = sequence_metadata.SequenceMetadata('gene1\tn\tG13T\tN\tconfers killer rabbit resistance')
        meta4 = sequence_metadata.SequenceMetadata("gene2\tp\tI42L\tY\tremoves tardigrade's space-living capability")

        expected_metadata = {
            'gene1': {
                'n': {12: {meta3}, 41: {meta1, meta2}},
                'p': {},
                '.': set(),
            },
            'gene2': {
                'n': {},
                'p': {41: {meta4}},
                '.': set(),
            }
        }
        ref_data = reference_data.ReferenceData(presence_absence_fa=presence_absence_fa, metadata_tsv=tsv_file)
        self.assertEqual(expected_metadata, ref_data.metadata)

        expected_seqs_dict = {
            'presence_absence': {
                'gene1': pyfastaq.sequences.Fasta('gene1', 'CATTCCTAGCGTCGTCTATCGTCG'),
                'gene2': pyfastaq.sequences.Fasta('gene2', 'AAAAACCCCGGGGTTTT')
            },
            'variants_only': {},
            'non_coding': {},
        }

        self.assertEqual(expected_seqs_dict, ref_data.seq_dicts)


    def test_dict_keys_intersection(self):
        '''Test dict_keys_intersection'''
        d1 = {'a': 1, 'b':2, 'c': 42}
        d2 = {'a': 42}
        d3 = {'a': 11, 'b': 'xyz'}
        self.assertEqual({'a'}, reference_data.ReferenceData._dict_keys_intersection([d1, d2, d3]))


    def test_get_filename(self):
        '''Test _get_filename'''
        file_that_exists_abs = os.path.join(data_dir, 'reference_data_get_filename')
        file_that_exists_rel = os.path.relpath(file_that_exists_abs)
        self.assertEqual(file_that_exists_abs, reference_data.ReferenceData._get_filename(file_that_exists_rel))
        self.assertIsNone(reference_data.ReferenceData._get_filename(None))

        with self.assertRaises(reference_data.Error):
            reference_data.ReferenceData._get_filename('thisisnotafilesoshouldthrowerror,unlessyoujustmadeitwhichseemslikeanoddthingtodoandyoudeservethefailingtest')


    def test_load_metadata_tsv(self):
        '''Test _load_metadata_tsv'''
        meta1 = sequence_metadata.SequenceMetadata('gene1\tn\tA42G\tN\tfree text')
        meta2 = sequence_metadata.SequenceMetadata('gene1\tn\tG13T\tN\tconfers killer rabbit resistance')
        meta3 = sequence_metadata.SequenceMetadata("gene2\tp\tI42L\tY\tremoves tardigrade's space-living capability")
        expected = {
            'gene1': {
                'n': {12: {meta2}, 41: {meta1}},
                'p': {},
                '.': set(),
            },
            'gene2': {
                'n': {},
                'p': {41: {meta3}},
                '.': set(),
            }
        }

        tsv_file = os.path.join(data_dir, 'reference_data_load_metadata_tsv.tsv')
        self.assertEqual(expected, reference_data.ReferenceData._load_metadata_tsv(tsv_file))


    def test_load_fasta_file(self):
        '''Test _load_fasta_file'''
        expected = {'seq1': pyfastaq.sequences.Fasta('seq1', 'ACGT')}
        filename = os.path.join(data_dir, 'reference_data_load_fasta_file.fa')
        got = reference_data.ReferenceData._load_fasta_file(filename)
        self.assertEqual(expected, got)


    def test_find_gene_in_seqs(self):
        '''Test _find_gene_in_seqs'''
        seqs_dict = {
            'dict1': {'name1': 'seq1', 'name2': 'seq2'},
            'dict2': {'name3': 'seq3'}
        }
        self.assertEqual(None, reference_data.ReferenceData._find_gene_in_seqs('name42', seqs_dict))
        self.assertEqual('dict1', reference_data.ReferenceData._find_gene_in_seqs('name1', seqs_dict))
        self.assertEqual('dict1', reference_data.ReferenceData._find_gene_in_seqs('name2', seqs_dict))
        self.assertEqual('dict2', reference_data.ReferenceData._find_gene_in_seqs('name3', seqs_dict))


    def test_write_metadata_tsv(self):
        '''Test _write_metadata_tsv'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_write_metadata_tsv_presence_absence.fa')
        metadata_tsv_in = os.path.join(data_dir, 'reference_data_write_metadata_tsv.tsv')
        metadata_tsv_expected = os.path.join(data_dir, 'reference_data_write_metadata_tsv.expected.tsv')
        tmp_tsv = 'tmp.test_write_metadata_tsv.out.tsv'
        ref_data = reference_data.ReferenceData(presence_absence_fa=presence_absence_fa, metadata_tsv=metadata_tsv_in)
        ref_data._write_metadata_tsv(ref_data.metadata, tmp_tsv)
        self.assertTrue(filecmp.cmp(metadata_tsv_expected, tmp_tsv, shallow=False))
        os.unlink(tmp_tsv)


    def test_write_dict_of_sequences(self):
        '''Test _write_dict_of_sequences'''
        d = {
            'seq1': pyfastaq.sequences.Fasta('seq1', 'ACGT'),
            'seq2': pyfastaq.sequences.Fasta('seq2', 'GGGG'),
        }
        tmp_file = 'tmp.test_write_dict_of_sequences.fa'
        reference_data.ReferenceData._write_dict_of_sequences(d, tmp_file)
        expected = os.path.join(data_dir, 'reference_data_write_dict_of_sequences.fa')
        self.assertTrue(filecmp.cmp(expected, tmp_file, shallow=False))
        os.unlink(tmp_file)


    def test_filter_bad_variant_data(self):
        '''Test _filter_bad_variant_data'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_presence_absence.in.fa')
        expected_presence_absence_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_presence_absence.expected.fa')
        variants_only_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_variants_only.in.fa')
        expected_variants_only_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_variants_only.expected.fa')
        non_coding_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_non_coding.in.fa')
        expected_non_coding_fa = os.path.join(data_dir, 'reference_data_filter_bad_data_non_coding.expected.fa')
        metadata_tsv = os.path.join(data_dir, 'reference_data_filter_bad_data_metadata.in.tsv')
        expected_tsv = os.path.join(data_dir, 'reference_data_filter_bad_data_metadata.expected.tsv')
        refdata = reference_data.ReferenceData(
            presence_absence_fa=presence_absence_fa,
            variants_only_fa=variants_only_fa,
            non_coding_fa=non_coding_fa,
            metadata_tsv=metadata_tsv
        )

        outprefix = 'tmp.test_filter_bad_variant_data'
        refdata._filter_bad_variant_data(outprefix, set(), set())

        self.assertTrue(filecmp.cmp(expected_tsv, outprefix + '.tsv'))
        self.assertTrue(filecmp.cmp(expected_variants_only_fa, outprefix + '.variants_only.fa'))
        self.assertTrue(filecmp.cmp(expected_presence_absence_fa, outprefix + '.presence_absence.fa'))
        self.assertTrue(filecmp.cmp(expected_non_coding_fa, outprefix + '.non_coding.fa'))
        os.unlink(outprefix + '.tsv')
        os.unlink(outprefix + '.variants_only.fa')
        os.unlink(outprefix + '.presence_absence.fa')
        os.unlink(outprefix + '.non_coding.fa')
        os.unlink(outprefix + '.log')


    def test_gene_seq_is_ok(self):
        '''Test _gene_seq_is_ok'''
        tests = [
            (pyfastaq.sequences.Fasta('x', 'ACGTG'), False, 'Remove: too short. Length: 5'),
            (pyfastaq.sequences.Fasta('x', 'A' * 100), False, 'Remove: too long. Length: 100'),
            (pyfastaq.sequences.Fasta('x', 'GAGGAGCCG'), False, 'Does not look like a gene (does not start with start codon, length (9) is not a multiple of 3 (length/3=3.0), or contains internal stop codons). Translation: EEP'),
            (pyfastaq.sequences.Fasta('x', 'ATGTAACCT'), False, 'Does not look like a gene (does not start with start codon, length (9) is not a multiple of 3 (length/3=3.0), or contains internal stop codons). Translation: M*P'),
            (pyfastaq.sequences.Fasta('x', 'ATGCCTGAG'), True, None)
        ]

        for seq, ok, message in tests:
            self.assertEqual((ok, message), reference_data.ReferenceData._gene_seq_is_ok(seq, 6, 99))


    def test_remove_bad_genes(self):
        '''Test _remove_bad_genes'''
        presence_absence_fasta = os.path.join(data_dir, 'reference_data_remove_bad_genes.in.fa')
        refdata = reference_data.ReferenceData(presence_absence_fa=presence_absence_fasta, max_gene_length=99)
        tmp_log = 'tmp.test_remove_bad_genes.log'

        expected_removed = {'g1', 'g2', 'g3', 'g4'}
        got_removed = refdata._remove_bad_genes(refdata.seq_dicts['presence_absence'], tmp_log)
        self.assertEqual(expected_removed, got_removed)

        expected_dict = {
            'g5': pyfastaq.sequences.Fasta('g5', 'ATGCCTGAG')
        }
        self.assertEqual(expected_dict, refdata.seq_dicts['presence_absence'])
        expected_log = os.path.join(data_dir, 'reference_data_test_remove_bad_genes.log')
        self.assertTrue(filecmp.cmp(expected_log, tmp_log, shallow=False))
        os.unlink(tmp_log)


    def test_make_catted_fasta(self):
        '''Test make_catted_fasta'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_make_catted_fasta.presence_absence.fa')
        variants_only_fa = os.path.join(data_dir, 'reference_data_make_catted_fasta.variants_only.fa')
        noncoding_fa = os.path.join(data_dir, 'reference_data_make_catted_fasta.noncoding.fa')
        expected_fa = os.path.join(data_dir, 'reference_data_make_catted_fasta.expected.fa')
        refdata = reference_data.ReferenceData(
            presence_absence_fa=presence_absence_fa,
            variants_only_fa=variants_only_fa,
            non_coding_fa=noncoding_fa
        )
        tmp_out = 'tmp.test.make_catted_fasta.out.fa'
        refdata.make_catted_fasta(tmp_out)
        self.assertTrue(filecmp.cmp(expected_fa, tmp_out, shallow=False))
        os.unlink(tmp_out)


    def test_sequence_type(self):
        '''Test sequence_type'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_sequence_type.presence_absence.fa')
        variants_only_fa = os.path.join(data_dir, 'reference_data_sequence_type.variants_only.fa')
        noncoding_fa = os.path.join(data_dir, 'reference_data_sequence_type.noncoding.fa')
        refdata = reference_data.ReferenceData(
            presence_absence_fa=presence_absence_fa,
            variants_only_fa=variants_only_fa,
            non_coding_fa=noncoding_fa
        )

        tests = [
            ('pa', 'presence_absence'),
            ('var_only', 'variants_only'),
            ('noncoding', 'non_coding'),
            ('not_there', None)
        ]

        for name, expected in tests:
            self.assertEqual(expected, refdata.sequence_type(name))


    def test_sequence(self):
        '''Test sequence'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_sequence.presence_absence.fa')
        expected = pyfastaq.sequences.Fasta('pa', 'ATGTTTTAA')
        refdata = reference_data.ReferenceData(presence_absence_fa=presence_absence_fa)
        self.assertEqual(expected, refdata.sequence('pa'))


    def test_sequence_length(self):
        '''Test sequence_length'''
        presence_absence_fa = os.path.join(data_dir, 'reference_data_sequence_length.presence_absence.fa')
        refdata = reference_data.ReferenceData(presence_absence_fa=presence_absence_fa)
        self.assertEqual(9, refdata.sequence_length('pa'))


    def test_all_non_wild_type_variants(self):
        '''Test all_non_wild_type_variants'''
        tsv_file = os.path.join(data_dir, 'reference_data_test_all_non_wild_type_variants.tsv')
        presence_absence_fa = os.path.join(data_dir, 'reference_data_test_all_non_wild_type_variants.ref.pres_abs.fa')
        variants_only_fa = os.path.join(data_dir, 'reference_data_test_all_non_wild_type_variants.ref.var_only.fa')
        noncoding_fa = os.path.join(data_dir, 'reference_data_test_all_non_wild_type_variants.ref.noncoding.fa')

        refdata = reference_data.ReferenceData(
            presence_absence_fa=presence_absence_fa,
            variants_only_fa=variants_only_fa,
            non_coding_fa=noncoding_fa,
            metadata_tsv=tsv_file
        )

        m1 = sequence_metadata.SequenceMetadata('var_only_gene\tn\tG9C\tN\tref has variant C instead of G')
        m2 = sequence_metadata.SequenceMetadata('var_only_gene\tp\tI5V\tN\tref has variant V instead of I')
        m3 = sequence_metadata.SequenceMetadata('var_only_gene\tp\tF6I\tY\tref has wild type F')
        m4 = sequence_metadata.SequenceMetadata('presence_absence_gene\tn\tA6C\tN\tref has variant C instead of A')
        m5 = sequence_metadata.SequenceMetadata('presence_absence_gene\tp\tA4G\tN\tref has variant G instead of A')
        m6 = sequence_metadata.SequenceMetadata('non_coding\tn\tC4T\tN\tref has variant T instead of C')

        self.assertEqual({'n': {8: {m1}}, 'p': {4: {m2}, 5: {m3}}}, refdata.all_non_wild_type_variants('var_only_gene'))
        self.assertEqual({'n': {5: {m4}}, 'p': {3: {m5}}}, refdata.all_non_wild_type_variants('presence_absence_gene'))
        self.assertEqual({'n': {3: {m6}}, 'p': {}}, refdata.all_non_wild_type_variants('non_coding'))
        self.assertEqual({'n': {}, 'p': {}}, refdata.all_non_wild_type_variants('not_a_known_sequence'))


    def test_write_cluster_allocation_file(self):
        '''Test write_cluster_allocation_file'''
        clusters = {
            'presence_absence': {
                'seq1': {'seq1', 'seq2'},
                'seq3': {'seq3', 'seq4', 'seq5'},
                'seq6': {'seq6'}
            },
            'non_coding' : {
                'seq10': {'seq42'}
            },
            'variants_only': None
        }
        tmpfile = 'tmp.test_write_cluster_allocation_file.out'
        reference_data.ReferenceData.write_cluster_allocation_file(clusters, tmpfile)
        expected_file = os.path.join(data_dir, 'reference_data_test_write_cluster_allocation_file.expected')
        self.assertTrue(filecmp.cmp(expected_file, tmpfile, shallow=False))
        os.unlink(tmpfile)


    def test_cluster_with_cdhit(self):
        '''Test cluster_with_cd_hit'''
        inprefix = os.path.join(data_dir, 'reference_data_test_cluster_with_cdhit')
        presence_absence_fa = inprefix + '.presence_absence.fa'
        non_coding_fa = inprefix + '.non_coding.fa'

        refdata = reference_data.ReferenceData(
            presence_absence_fa=presence_absence_fa,
            non_coding_fa=non_coding_fa,
        )

        outprefix = 'tmp.test_cluster_with_cdhit'

        expected = {
            'non_coding': {
                'noncoding1': {'noncoding1'}
            },
            'presence_absence': {
                'presence_absence1': {'presence_absence1', 'presence_absence2'},
                'presence_absence3': {'presence_absence4', 'presence_absence3'}
            },
            'variants_only': None,
        }

        got = refdata.cluster_with_cdhit(inprefix, outprefix)
        self.assertEqual(expected, got)
        all_seqs = {}
        pyfastaq.tasks.file_to_dict(presence_absence_fa, all_seqs)
        pyfastaq.tasks.file_to_dict(non_coding_fa, all_seqs)
        expected_seqs = {x: all_seqs[x] for x in ['presence_absence1', 'presence_absence3', 'noncoding1']}
        got_seqs = {}
        pyfastaq.tasks.file_to_dict(outprefix + '.cluster_representatives.fa', got_seqs)
        self.assertEqual(expected_seqs, got_seqs)

        expected_clusters_file = os.path.join(data_dir, 'reference_data_test_cluster_with_cdhit.clusters.tsv')
        got_clusters_file = outprefix + '.clusters.tsv'
        self.assertTrue(filecmp.cmp(expected_clusters_file, got_clusters_file, shallow=False))

        os.unlink(got_clusters_file)
        os.unlink(outprefix + '.cluster_representatives.fa')
        os.unlink(outprefix + '.non_coding.cdhit')
        os.unlink(outprefix + '.presence_absence.cdhit')


    def test_write_seqs_to_fasta(self):
        '''Test write_seqs_to_fasta'''
        refdata = reference_data.ReferenceData(presence_absence_fa=os.path.join(data_dir, 'reference_data_test_write_seqs_to_fasta.in.fa'))
        expected_outfile = os.path.join(data_dir, 'reference_data_test_write_seqs_to_fasta.expected.fa')
        tmpfile = 'tmp.test.reference_data.write_seqs_to_fasta.out.fa'
        refdata.write_seqs_to_fasta(tmpfile, {'seq1', 'seq4', 'seq5'})
        self.assertTrue(filecmp.cmp(expected_outfile, tmpfile, shallow=False))
        os.unlink(tmpfile)
