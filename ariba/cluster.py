import signal
import os
import atexit
import random
import math
import shutil
import sys
import pyfastaq
from ariba import assembly, assembly_compare, assembly_variants, bam_parse, best_seq_chooser, external_progs, flag, mapping, report, samtools_variants

class Error (Exception): pass

unittest=False

class Cluster:
    def __init__(self,
      root_dir,
      name,
      refdata,
      total_reads,
      total_reads_bases,
      fail_file=None,
      read_store=None,
      reference_names=None,
      logfile=None,
      assembly_coverage=50,
      assembly_kmer=21,
      assembler='spades',
      max_insert=1000,
      min_scaff_depth=10,
      nucmer_min_id=90,
      nucmer_min_len=20,
      nucmer_breaklen=200,
      reads_insert=500,
      sspace_k=20,
      sspace_sd=0.4,
      threads=1,
      bcf_min_dp=10,
      bcf_min_dv=5,
      bcf_min_dv_over_dp=0.3,
      bcf_min_qual=20,
      assembled_threshold=0.95,
      unique_threshold=0.03,
      max_gene_nt_extend=30,
      bowtie2_preset='very-sensitive-local',
      spades_other_options=None,
      clean=True,
      extern_progs=None,
      random_seed=42,
    ):
        self.root_dir = os.path.abspath(root_dir)
        self.read_store = read_store
        self.refdata = refdata
        self.name = name
        self.fail_file = fail_file
        self.reference_fa = os.path.join(self.root_dir, 'reference.fa')
        self.reference_names = reference_names
        self.all_reads1 = os.path.join(self.root_dir, 'reads_1.fq')
        self.all_reads2 = os.path.join(self.root_dir, 'reads_2.fq')
        self.references_fa = os.path.join(self.root_dir, 'references.fa')

        if os.path.exists(self.root_dir):
            self._input_files_exist()

        self.total_reads = total_reads
        self.total_reads_bases = total_reads_bases
        self.logfile = logfile
        self.assembly_coverage = assembly_coverage
        self.assembly_kmer = assembly_kmer
        self.assembler = assembler
        self.sspace_k = sspace_k
        self.sspace_sd = sspace_sd
        self.reads_insert = reads_insert
        self.spades_other_options = spades_other_options

        self.reads_for_assembly1 = os.path.join(self.root_dir, 'reads_for_assembly_1.fq')
        self.reads_for_assembly2 = os.path.join(self.root_dir, 'reads_for_assembly_2.fq')

        self.ref_sequence = None

        self.max_insert = max_insert
        self.min_scaff_depth = min_scaff_depth

        self.nucmer_min_id = nucmer_min_id
        self.nucmer_min_len = nucmer_min_len
        self.nucmer_breaklen = nucmer_breaklen

        self.bcf_min_dp = bcf_min_dp
        self.bcf_min_dv = bcf_min_dv
        self.bcf_min_dv_over_dp = bcf_min_dv_over_dp
        self.bcf_min_qual = bcf_min_qual

        self.bowtie2_preset = bowtie2_preset

        self.threads = threads
        self.assembled_threshold = assembled_threshold
        self.unique_threshold = unique_threshold
        self.max_gene_nt_extend = max_gene_nt_extend
        self.status_flag = flag.Flag()
        self.clean = clean

        self.assembly_dir = os.path.join(self.root_dir, 'Assembly')
        self.final_assembly_fa = os.path.join(self.root_dir, 'assembly.fa')
        self.final_assembly_bam = os.path.join(self.root_dir, 'assembly.reads_mapped.bam')
        self.final_assembly_read_depths = os.path.join(self.root_dir, 'assembly.reads_mapped.bam.read_depths.gz')
        self.final_assembly_vcf = os.path.join(self.root_dir, 'assembly.reads_mapped.bam.vcf')
        self.samtools_vars_prefix = self.final_assembly_bam
        self.assembly_compare = None
        self.assembly_compare_prefix = os.path.join(self.root_dir, 'assembly_compare')

        self.mummer_variants = {}
        self.variant_depths = {}
        self.percent_identities = {}

        # The log filehandle self.log_fh is set at the start of the run() method.
        # Lots of other methods use self.log_fh. But for unit testing, run() isn't
        # run. So we need to set this to something for unit testing.
        # On the other hand, setting it here breaks a real run of ARIBA because
        # multiprocessing complains with the error:
        # TypeError: cannot serialize '_io.TextIOWrapper' object.
        # Hence the following two lines...
        if unittest:
            self.log_fh = sys.stdout
        else:
            atexit.register(self._atexit)
            self.log_fh = None

        if extern_progs is None:
            self.extern_progs = external_progs.ExternalProgs()
        else:
            self.extern_progs = extern_progs

        self.random_seed = random_seed
        wanted_signals = [signal.SIGABRT, signal.SIGINT, signal.SIGSEGV, signal.SIGTERM]
        for s in wanted_signals:
            signal.signal(s, self._receive_signal)


    def _atexit(self):
        if self.log_fh is not None:
            pyfastaq.utils.close(self.log_fh)
            self.log_fh = None


    def _receive_signal(self, signum, stack):
        print('Signal', signum, 'received in cluster', self.name + '... Stopping!', file=sys.stderr, flush=True)
        if self.log_fh is not None:
            pyfastaq.utils.close(self.log_fh)
            self.log_fh = None
        if self.fail_file is not None:
            with open(self.fail_file, 'w') as f:
                pass
        sys.exit(1)


    def _input_files_exist(self):
        assert self.read_store is None
        if not (os.path.exists(self.all_reads1) and os.path.exists(self.all_reads2)):
            raise Error('Error making cluster. Reads files not found')
        if not os.path.exists(self.references_fa):
            raise Error('Error making cluster. References fasta not found')


    def _set_up_input_files(self):
        if os.path.exists(self.root_dir):
            self._input_files_exist()
        else:
            assert self.read_store is not None
            assert self.reference_names is not None
            try:
                os.mkdir(self.root_dir)
            except:
                raise Error('Error making directory ' + self.root_dir)
            self.read_store.get_reads(self.name, self.all_reads1, self.all_reads2)
            self.refdata.write_seqs_to_fasta(self.references_fa, self.reference_names)


    def _clean_file(self, filename):
        if self.clean:
            print('Deleting file', filename, file=self.log_fh)
            os.unlink(filename)


    def _clean(self):
        if not self.clean:
            print('   ... not deleting anything because --noclean used', file=self.log_fh, flush=True)
            return


        to_delete = [
            'assembly.fa',
            'assembly.fa.fai',
            'assembly_compare.nucmer.coords',
            'assembly_compare.nucmer.coords.snps',
            'assembly.reads_mapped.bam.bai',
            'assembly.reads_mapped.bam.vcf',
            'assembly.reads_mapped.bam',
            'assembly.reads_mapped.bam.read_depths.gz',
            'assembly.reads_mapped.bam.read_depths.gz.tbi',
            'reads_1.fq',
            'reads_2.fq',
            'reference.fa',
        ]

        to_delete = [os.path.join(self.root_dir, x) for x in to_delete]

        for filename in to_delete:
            if os.path.exists(filename):
                self._clean_file(filename)


    @staticmethod
    def _number_of_reads_for_assembly(reference_fa, insert_size, total_bases, total_reads, coverage):
        file_reader = pyfastaq.sequences.file_reader(reference_fa)
        ref_length = sum([len(x) for x in file_reader])
        assert ref_length > 0
        ref_length += 2 * insert_size
        mean_read_length = total_bases / total_reads
        wanted_bases = coverage * ref_length
        wanted_reads = int(math.ceil(wanted_bases / mean_read_length))
        wanted_reads += wanted_reads % 2
        return wanted_reads


    @staticmethod
    def _make_reads_for_assembly(number_of_wanted_reads, total_reads, reads_in1, reads_in2, reads_out1, reads_out2, random_seed=None):
        '''Makes fastq files that are random subset of input files. Returns total number of reads in output files.
           If the number of wanted reads is >= total reads, then just makes symlinks instead of making
           new copies of the input files.'''
        random.seed(random_seed)

        if number_of_wanted_reads < total_reads:
            reads_written = 0
            percent_wanted = 100 * number_of_wanted_reads / total_reads
            file_reader1 = pyfastaq.sequences.file_reader(reads_in1)
            file_reader2 = pyfastaq.sequences.file_reader(reads_in2)
            out1 = pyfastaq.utils.open_file_write(reads_out1)
            out2 = pyfastaq.utils.open_file_write(reads_out2)

            for read1 in file_reader1:
                try:
                    read2 = next(file_reader2)
                except StopIteration:
                    pyfastaq.utils.close(out1)
                    pyfastaq.utils.close(out2)
                    raise Error('Error subsetting reads. No mate found for read ' + read1.id)

                if random.randint(0, 100) <= percent_wanted:
                    print(read1, file=out1)
                    print(read2, file=out2)
                    reads_written += 2

            pyfastaq.utils.close(out1)
            pyfastaq.utils.close(out2)
            return reads_written
        else:
            os.symlink(reads_in1, reads_out1)
            os.symlink(reads_in2, reads_out2)
            return total_reads


    def run(self):
        self._set_up_input_files()

        for fname in [self.all_reads1, self.all_reads2, self.references_fa]:
            if not os.path.exists(fname):
                raise Error('File ' + fname + ' not found. Cannot continue')

        if self.logfile is None:
            self.logfile = os.path.join(self.root_dir, 'log.txt')

        self.log_fh = pyfastaq.utils.open_file_write(self.logfile)

        original_dir = os.getcwd()
        os.chdir(self.root_dir)

        try:
            self._run()
        except Error as err:
            os.chdir(original_dir)
            print('Error running cluster! Error was:', err, sep='\n', file=self.log_fh)
            pyfastaq.utils.close(self.log_fh)
            self.log_fh = None
            raise Error('Error running cluster ' + self.name + '!')

        os.chdir(original_dir)
        print('Finished', file=self.log_fh, flush=True)
        print('{:_^79}'.format(' LOG FILE END ' + self.name + ' '), file=self.log_fh, flush=True)

        # This stops multiprocessing complaining with the error:
        # multiprocessing.pool.MaybeEncodingError: Error sending result: '[<ariba.cluster.Cluster object at 0x7ffa50f8bcd0>]'. Reason: 'TypeError("cannot serialize '_io.TextIOWrapper' object",)'
        pyfastaq.utils.close(self.log_fh)
        self.log_fh = None


    def _run(self):
        print('{:_^79}'.format(' LOG FILE START ' + self.name + ' '), file=self.log_fh, flush=True)

        print('Choosing best reference sequence:', file=self.log_fh, flush=True)
        seq_chooser = best_seq_chooser.BestSeqChooser(
            self.all_reads1,
            self.all_reads2,
            self.references_fa,
            self.log_fh,
            samtools_exe=self.extern_progs.exe('samtools'),
            bowtie2_exe=self.extern_progs.exe('bowtie2'),
            bowtie2_preset=self.bowtie2_preset,
            threads=1,
        )
        self.ref_sequence = seq_chooser.best_seq(self.reference_fa)
        self._clean_file(self.references_fa)
        self._clean_file(self.references_fa + '.fai')

        if self.ref_sequence is None:
            self.status_flag.add('ref_seq_choose_fail')
            self.assembled_ok = False
        else:
            wanted_reads = self._number_of_reads_for_assembly(self.reference_fa, self.reads_insert, self.total_reads_bases, self.total_reads, self.assembly_coverage)
            made_reads = self._make_reads_for_assembly(wanted_reads, self.total_reads, self.all_reads1, self.all_reads2, self.reads_for_assembly1, self.reads_for_assembly2, random_seed=self.random_seed)
            print('\nUsing', made_reads, 'from a total of', self.total_reads, 'for assembly.', file=self.log_fh, flush=True)
            print('Assembling reads:', file=self.log_fh, flush=True)
            self.ref_sequence_type = self.refdata.sequence_type(self.ref_sequence.id)
            assert self.ref_sequence_type is not None
            self.assembly = assembly.Assembly(
              self.reads_for_assembly1,
              self.reads_for_assembly2,
              self.reference_fa,
              self.assembly_dir,
              self.final_assembly_fa,
              self.final_assembly_bam,
              self.log_fh,
              scaff_name_prefix=self.ref_sequence.id,
              kmer=self.assembly_kmer,
              assembler=self.assembler,
              spades_other_options=self.spades_other_options,
              sspace_k=self.sspace_k,
              sspace_sd=self.sspace_sd,
              reads_insert=self.reads_insert,
              extern_progs=self.extern_progs,
              clean=self.clean
            )

            self.assembly.run()
            self.assembled_ok = self.assembly.assembled_ok
            self._clean_file(self.reads_for_assembly1)
            self._clean_file(self.reads_for_assembly2)
            if self.clean:
                print('Deleting Assembly directory', self.assembly_dir, file=self.log_fh, flush=True)
                shutil.rmtree(self.assembly_dir)

        if self.assembled_ok:
            print('\nAssembly was successful\n\nMapping reads to assembly:', file=self.log_fh, flush=True)

            mapping.run_bowtie2(
                self.all_reads1,
                self.all_reads2,
                self.final_assembly_fa,
                self.final_assembly_bam[:-4],
                threads=1,
                sort=True,
                samtools=self.extern_progs.exe('samtools'),
                bowtie2=self.extern_progs.exe('bowtie2'),
                bowtie2_preset=self.bowtie2_preset,
                verbose=True,
                verbose_filehandle=self.log_fh
            )

            if self.assembly.has_contigs_on_both_strands:
                self.status_flag.add('hit_both_strands')

            print('\nMaking and checking scaffold graph', file=self.log_fh, flush=True)

            if not self.assembly.scaff_graph_ok:
                self.status_flag.add('scaffold_graph_bad')

            print('Comparing assembly against reference sequence', file=self.log_fh, flush=True)
            self.assembly_compare = assembly_compare.AssemblyCompare(
              self.final_assembly_fa,
              self.assembly.sequences,
              self.reference_fa,
              self.ref_sequence,
              self.assembly_compare_prefix,
              self.refdata,
              nucmer_min_id=self.nucmer_min_id,
              nucmer_min_len=self.nucmer_min_len,
              nucmer_breaklen=self.nucmer_breaklen,
              assembled_threshold=self.assembled_threshold,
              unique_threshold=self.unique_threshold,
              max_gene_nt_extend=self.max_gene_nt_extend,
            )
            self.assembly_compare.run()
            self.status_flag = self.assembly_compare.update_flag(self.status_flag)

            nucmer_hits_to_ref = assembly_compare.AssemblyCompare.nucmer_hits_to_ref_coords(self.assembly_compare.nucmer_hits)
            assembly_variants_obj = assembly_variants.AssemblyVariants(self.refdata, self.assembly_compare.nucmer_snps_file)
            self.assembly_variants = assembly_variants_obj.get_variants(self.ref_sequence.id, nucmer_hits_to_ref)

            for var_list in self.assembly_variants.values():
                for var in var_list:
                    if var[3] not in ['.', 'SYN', None]:
                        self.status_flag.add('has_nonsynonymous_variants')
                        break

                if self.status_flag.has('has_nonsynonymous_variants'):
                    break


            print('\nCalling variants with samtools:', file=self.log_fh, flush=True)

            self.samtools_vars = samtools_variants.SamtoolsVariants(
                self.final_assembly_fa,
                self.final_assembly_bam,
                self.samtools_vars_prefix,
                log_fh=self.log_fh,
                samtools_exe=self.extern_progs.exe('samtools'),
                bcftools_exe=self.extern_progs.exe('bcftools'),
                bcf_min_dp=self.bcf_min_dp,
                bcf_min_dv=self.bcf_min_dv,
                bcf_min_dv_over_dp=self.bcf_min_dv_over_dp,
                bcf_min_qual=self.bcf_min_qual,
            )
            self.samtools_vars.run()

            self.total_contig_depths = self.samtools_vars.total_depth_per_contig(self.samtools_vars.read_depths_file)

            if self.samtools_vars.variants_in_coords(self.assembly_compare.assembly_match_coords(), self.samtools_vars.vcf_file):
                self.status_flag.add('variants_suggest_collapsed_repeat')
        else:
            print('\nAssembly failed\n', file=self.log_fh, flush=True)
            self.status_flag.add('assembly_fail')


        print('\nMaking report lines', file=self.log_fh, flush=True)
        self.report_lines = report.report_lines(self)
        self._clean()
        atexit.unregister(self._atexit)
