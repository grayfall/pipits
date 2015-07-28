#!/usr/bin/env python

import sys, os, argparse, shutil, subprocess, textwrap
import runcmd as rc
import tcolours as tc
import dependencies as pd

__author__ = "Hyun Soon Gweon"
__copyright__ = "Copyright 2015, The PIPITS Project"
__credits__ = ["Hyun Soon Gweon", "Anna Oliver", "Joanne Taylor", "Tim Booth", "Melanie Gibbs", "Daniel S. Read", "Robert I. Griffiths", "Karsten Schonrogge"]
__license__ = "GPL"
__maintainer__ = "Hyun Soon Gweon"
__email__ = "hyugwe@ceh.ac.uk"


def run(options):

    PIPITS_PREP_OUTPUT = "prepped.fasta"


    # Make directories (outdir and tmpdir)
    if not os.path.exists(options.outDir):
        os.mkdir(options.outDir)
    else:
        shutil.rmtree(options.outDir)
        os.mkdir(options.outDir)

    tmpDir = options.outDir + "/intermediate"
    if not os.path.exists(tmpDir):
        os.mkdir(tmpDir)


    # Logging
    import logging
    logger = logging.getLogger("pipits_prep")
    logger.setLevel(logging.DEBUG)

    streamLoggerFormatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", tc.HEADER + "%Y-%m-%d %H:%M:%S" + tc.ENDC)
    streamLogger = logging.StreamHandler()
    if options.verbose:
        streamLogger.setLevel(logging.DEBUG)
    else:
        streamLogger.setLevel(logging.INFO)
    streamLogger.setFormatter(streamLoggerFormatter)
    logger.addHandler(streamLogger)

    fileLoggerFormatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s", tc.HEADER + "%Y-%m-%d %H:%M:%S" + tc.ENDC)
    fileLogger = logging.FileHandler(options.outDir + "/log.txt", "w")
    fileLogger.setLevel(logging.DEBUG)
    fileLogger.setFormatter(fileLoggerFormatter)
    logger.addHandler(fileLogger)

    # Summary file
    summary_file = open(options.outDir + "/summary_pipits_prep.txt", "w")

    # Start!
    logger.info(tc.OKBLUE + "PIPITS PREP started" + tc.ENDC)

    EXE_DIR = os.path.dirname(os.path.realpath(__file__))


    # Check for the presence of rawdata directory
    logger.debug("Checking for presence of input directory")
    if not os.path.exists(options.dataDir):
        logger.error("Cannot find \"" + options.dataDir + "\" directory. Ensure you have the correct name of the directory where your Illumina sequences are stored")
        exit(1)


    fastqs_l = []
    fastqs_f = []
    fastqs_r = []

    # if list is provided...
    if options.listfile:
        logger.info("Processing user-provided listfile")
        try:
            listfile = open(options.listfile, "r")
        except IOError:
            logger.error("\"" + options.listfile + "\" not found.")
            exit(1)

        for l in listfile:
            if l.strip(" ").strip("\n") != "" and not l.startswith("#"):
                l = l.rstrip().split("\t")
                fastqs_l.append(l[0])
                fastqs_f.append(l[1])
                fastqs_r.append(l[2])
        listfile.close()


    # if not provided
    if not options.listfile:
        logger.info("Getting list of fastq files and sample ID from input folder")
        fastqs = []
        for file in os.listdir(options.dataDir):
            if \
                    file.endswith(".fastq.gz") or \
                    file.endswith(".bz2") or \
                    file.endswith(".fastq"):
                fastqs.append(file)

        if len(fastqs) % 2 != 0:
            logger.error("There are missing pair(s) in the Illumina sequences. Check your files and labelling")
            exit(1)

        coin = True
        for fastq in sorted(fastqs):
            if coin == True:
                fastqs_f.append(fastq)
            else:
                fastqs_r.append(fastq)
            coin = not coin

        for i in range(len(fastqs_f)):
            if fastqs_f[i].split("_")[0] != fastqs_r[i].split("_")[0]:
                logger.error("Problem with labelling FASTQ files.")
                exit(1)
            fastqs_l.append(fastqs_f[i].split("_")[0])


    # Check
    if len(fastqs_f) != len(fastqs_r):
        logger.error("Different number of forward FASTQs and reverse FASTQs")
        exit(1)


    # Done loading. Now check the file extensions.
    filenameextensions = []
    for filename in (fastqs_f + fastqs_r):
        filenameextensions.append(filename.split(".")[-1].rstrip())
    if len(set(filenameextensions)) > 1:
        logger.error("More than two types of extensions")
        exit(1)
    extensionType = next(iter(filenameextensions))


    # For summary 1:
    logger.info("Counting sequences in rawdata")
    numberofsequences = 0
    for fr in fastqs_f:
        if extensionType == "gz":
            cmd = " ".join(["zcat", options.dataDir + "/" + fr, "|", "wc -l"])
        elif extensionType =="bz2":
            cmd = " ".join(["bzcat", options.dataDir + "/" + fr, "|", "wc -l"])
        elif extensionType =="fastq":
            cmd = " ".join(["cat", options.dataDir + "/" + fr, "|", "wc -l"])
        else:
            logger.error("Unknown extension type.")
            exit(1)

        logger.debug(cmd)
        p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        numberofsequences += int(p.communicate()[0]) / 4
        p.wait()
    logger.info("\t" + tc.RED + "Number of paired-end reads in rawdata: " + str(numberofsequences) + tc.ENDC)
    summary_file.write("Number of paired-end reads in rawdata: " + str(numberofsequences) + "\n")


    # Join paired-end reads                                                                                                                                                             
    logger.info("Joining paired-end reads" + "[" + options.joiner_method + "]")
    if not os.path.exists(tmpDir + "/joined"):
        os.mkdir(tmpDir + "/joined")

    for i in range(len(fastqs_l)):

        if extensionType == "gz":
            cmd = " ".join(["gunzip -c", options.dataDir + "/" + fastqs_f[i], ">", tmpDir + "/joined/" + fastqs_f[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
            cmd = " ".join(["gunzip -c", options.dataDir + "/" + fastqs_r[i], ">", tmpDir + "/joined/" + fastqs_r[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
        elif extensionType == "bz2":
            cmd = " ".join(["bunzip2 -c", options.dataDir + "/" + fastqs_f[i], ">", tmpDir + "/joined/" + fastqs_f[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
            cmd = " ".join(["bunzip2 -c", options.dataDir + "/" + fastqs_r[i], ">", tmpDir + "/joined/" + fastqs_r[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
        elif extensionType == "fastq":
            cmd = " ".join(["ln -sf", 
                            os.path.abspath(options.dataDir + "/" + fastqs_f[i]), 
                            tmpDir + "/joined/" + fastqs_f[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
            cmd = " ".join(["ln -sf",
                            os.path.abspath(options.dataDir + "/" + fastqs_r[i]),
                            tmpDir + "/joined/" + fastqs_r[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)
        else:
            print(extensionType)
            logger.error("Unknown extension found.")
            exit(1)
        
#        joiner_method = "PEAR"

        if options.joiner_method == "PEAR":
            cmd = " ".join([pd.PEAR,
                            "-f", tmpDir + "/joined/" + fastqs_f[i] + ".tmp",
                            "-r", tmpDir + "/joined/" + fastqs_r[i] + ".tmp",
                            "-o", tmpDir + "/joined/" + fastqs_l[i],
                            "-j", options.threads,
                            "-b", options.base_phred_quality_score,
                            "-q 30",
                            "-p 0.0001"])
            rc.run_cmd(cmd, logger, options.verbose)

            cmd = " ".join(["rm -v",
                            tmpDir + "/joined/" + fastqs_f[i] + ".tmp",
                            tmpDir + "/joined/" + fastqs_r[i] + ".tmp"])
            rc.run_cmd(cmd, logger, options.verbose)

            cmd = " ".join(["mv -f", 
                            tmpDir + "/joined/" + fastqs_l[i] + ".assembled.fastq", 
                            tmpDir + "/joined/" + fastqs_l[i] + ".joined.fastq"])
            rc.run_cmd(cmd, logger, options.verbose)

        elif options.joiner_method == "FASTQJOIN":
            cmd = " ".join(["fastq-join",
                            tmpDir + "/joined/" + fastqs_f[i] + ".tmp",
                            tmpDir + "/joined/" + fastqs_r[i] + ".tmp",
                            "-o",
                            tmpDir + "/joined/" + fastqs_l[i] + ".joined.fastq"])
            rc.run_cmd(cmd, logger, options.verbose)

            cmd = " ".join(["mv -f",
                            tmpDir + "/joined/" + fastqs_l[i] + ".joined.fastqjoin",
                            tmpDir + "/joined/"+ fastqs_l[i] +".joined.fastq"])
            rc.run_cmd(cmd, logger, options.verbose)


    # For summary 2:
    numberofsequences = 0
    for i in range(len(fastqs_l)):
        cmd = " ".join(["cat", tmpDir + "/joined/" + fastqs_l[i] + ".joined.fastq", "|", "wc -l"])
        logger.debug(cmd)
        p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        numberofsequences += int(p.communicate()[0]) / 4
        p.wait()
    logger.info("\t" + tc.RED + "Number of joined reads: " + str(numberofsequences) + tc.ENDC)
    summary_file.write("Number of joined reads: " + str(numberofsequences) + "\n")

    # Quality filter
    logger.info("Quality filtering [FASTX]")
    if not os.path.exists(tmpDir + "/fastqqualityfiltered"):
        os.mkdir(tmpDir + "/fastqqualityfiltered")

    for i in range(len(fastqs_f)):
        cmd = " ".join([pd.FASTX_FASTQ_QUALITY_FILTER,
                        "-i", tmpDir + "/joined/" + fastqs_l[i] + ".joined.fastq", 
                        "-o", tmpDir + "/fastqqualityfiltered/" + fastqs_l[i] + ".fastq", 
                        "-q", options.FASTX_fastq_quality_filter_q,
                        "-p", options.FASTX_fastq_quality_filter_p,
                        "-Q" + options.base_phred_quality_score])
        rc.run_cmd(cmd, logger, options.verbose)


    # For summary 3:
    numberofsequences = 0
    for i in range(len(fastqs_l)):
        cmd = " ".join(["cat", tmpDir + "/fastqqualityfiltered/" + fastqs_l[i] + ".fastq", "|", "wc -l"])
        p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        numberofsequences += int(p.communicate()[0]) / 4
        p.wait()
    logger.info("\t" + tc.RED + "Number of quality filtered reads: " + str(numberofsequences) + tc.ENDC)
    summary_file.write("Number of quality filtered reads: " + str(numberofsequences) + "\n")


    # Removing reads with \"N\" and FASTA conversion
    if options.FASTX_fastq_to_fasta_n:
        logger.info("Converting FASTQ to FASTA [FASTX]")
    else:
        logger.info("Converting FASTQ to FASTA and also removing reads with \"N\" nucleotide [FASTX]")

    if not os.path.exists(tmpDir + "/fastqtofasta"):
        os.mkdir(tmpDir + "/fastqtofasta")

    fastq_to_fasta_n = ""
    if options.FASTX_fastq_to_fasta_n:
        fastq_to_fasta_n = "-n"

    for i in range(len(fastqs_f)):
        cmd = " ".join([pd.FASTX_FASTQ_TO_FASTA, 
                        "-i", tmpDir + "/fastqqualityfiltered/" + fastqs_l[i] + ".fastq", 
                        "-o", tmpDir + "/fastqtofasta/" + fastqs_l[i] + ".fasta", 
                        "-Q33",
                        fastq_to_fasta_n])
        rc.run_cmd(cmd, logger, options.verbose)


    # For summary 3:
    numberofsequences = 0
    for i in range(len(fastqs_l)):
        cmd = " ".join(["grep \"^>\"", tmpDir + "/fastqtofasta/" + fastqs_l[i] + ".fasta", "|", "wc -l"])
        p = subprocess.Popen(cmd, shell=True, stdout = subprocess.PIPE)
        numberofsequences += int(p.communicate()[0])
        p.wait()
    logger.info("\t" + tc.RED + "Number of N-less quality filtered sequences: " + str(numberofsequences) + tc.ENDC)
    summary_file.write("Number of N-less quality filtered sequences: " + str(numberofsequences) + "\n")


    # Re-ID and re-index FASTA and merging them all
    logger.info("Re-IDing and indexing FASTA, and merging all into a single file")
    outfileFinalFASTA = open(options.outDir + "/" + PIPITS_PREP_OUTPUT, "w")
    for i in range(len(fastqs_f)):
        line_index = 1
        logger.debug("Reading " + tmpDir + "/fastqtofasta/" + fastqs_l[i] + ".fasta")
        infile_fasta = open(tmpDir + "/fastqtofasta/" + fastqs_l[i] + ".fasta")
        for line in infile_fasta:
            if line.startswith(">"):
                outfileFinalFASTA.write(">" + fastqs_l[i] + "_" + str(line_index) + "\n")
                line_index += 1
            else:
                outfileFinalFASTA.write(line.rstrip() + "\n")
    outfileFinalFASTA.close()


    # Clean up tmp_directory
    if options.remove:
        logger.info("Cleaning temporary directory")
        shutil.rmtree(tmpDir)


    logger.info(tc.OKBLUE + "PIPITS PREP ended successfully. \"" + PIPITS_PREP_OUTPUT + "\" created in \"" + options.outDir + "\"" + tc.ENDC)
    logger.info(tc.OKYELLOW + "Next Step: PIPITS FUNITS [ Suggestion: pipits_funits -i " + options.outDir + "/" + PIPITS_PREP_OUTPUT + " -o out_funits -x YOUR_ITS_SUBREGION ]" + tc.ENDC)
    print("")
    summary_file.close()
