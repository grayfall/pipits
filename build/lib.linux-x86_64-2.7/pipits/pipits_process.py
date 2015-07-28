#!/usr/bin/env python

import sys, os, argparse, subprocess, shutil, textwrap
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

    # Check file exists
    if not os.path.exists(options.input):
        print("Error: Input file doesn't exist")
        exit(1)


    EXE_DIR = os.path.dirname(os.path.realpath(__file__))
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
    logger = logging.getLogger("pipits_process")
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
    #summary_file = open(options.outDir + "/summary_pipits_process.txt", "w")

    # Start
    logger.info(tc.OKBLUE + "PIPITS PROCESS started" + tc.ENDC)


    # Check if the file is empty
    if os.stat(options.input).st_size == 0:
        logger.error("Input file is empty!")
        exit(0)
        
    # Derep with sgtk
    logger.info("Dereplicating and removing unique sequences prior to picking OTUs")
    cmd = " ".join([pd.VSEARCH, "--derep_fulllength", options.input, 
                    "--output", tmpDir + "/input_nr.fasta", 
                    "--minuniquesize 2", 
                    "--sizeout",
                    "--threads", options.threads])
    rc.run_cmd_VSEARCH(cmd, logger, options.verbose)
    #filesize = os.path.getsize(tmpDir + "/input_nr.fasta") / 1000.0
    #logger.info("Dereplicating " + tc.OKGREEN + "(Done) " + tc.ENDC)
    #logger.info("\t" + tc.RED + "File size after initial dereplication: " + str(filesize) + " MB" + tc.ENDC)

    # Check if the file is empty
    if os.stat(tmpDir + "/input_nr.fasta").st_size == 0:
        logger.info(tc.OKYELLOW + "After dereplicating and removing unique sequences, there aren't no sequences! Processing stopped." + tc.ENDC)
        exit(0)


    # OTU clustering
    logger.info("Picking OTUs [VSEARCH]")
    cmd = " ".join([pd.VSEARCH, 
                    "--cluster_fast", tmpDir + "/input_nr.fasta", 
                    "--id", options.VSEARCH_id,
                    "--centroids", tmpDir + "/input_nr_otus.fasta",
                    "--uc", tmpDir + "/input_nr_otus.uc",
                    "--threads", options.threads])
    rc.run_cmd_VSEARCH(cmd, logger, options.verbose)


    # Chimera removal
    logger.info("Removing chimeras [VSEARCH]")
    cmd = " ".join([pd.VSEARCH, 
                    "--uchime_ref", tmpDir + "/input_nr_otus.fasta", 
                    "--db", pd.UNITE_REFERENCE_DATA_CHIMERA, 
                    "--nonchimeras", tmpDir + "/input_nr_otus_nonchimeras.fasta",
                    "--threads", options.threads])
    rc.run_cmd_VSEARCH(cmd, logger, options.verbose)


    # Rename OTUs
    logger.info("Renaming OTUs")
    def renumberOTUS():
        handle_in = open(tmpDir + "/input_nr_otus_nonchimeras.fasta", "rU")
        handle_out = open(tmpDir + "/input_nr_otus_nonchimeras_relabelled.fasta", "w")
        for line in handle_in:
            if line.startswith(">"):
                newlabel = line[1:].split(";")[0]
                handle_out.write(">" + newlabel + "\n")
            else:
                handle_out.write(line.rstrip() + "\n")
        handle_in.close()
        handle_out.close()
    renumberOTUS()


    # Map reads to OTUs
    logger.info("Mapping reads onto centroids [VSEARCH]")
    cmd = " ".join([pd.VSEARCH, 
                    "--usearch_global", options.input, 
                    "--db", tmpDir + "/input_nr_otus_nonchimeras_relabelled.fasta", 
                    "--id", options.VSEARCH_id, 
                    "--uc", tmpDir + "/otus.uc",
                    "--threads", options.threads])
    rc.run_cmd_VSEARCH(cmd, logger, options.verbose)


    # OTU construction
    logger.info("Making OTU table")
    cmd = " ".join(["python", EXE_DIR + "/pipits_uc/uc2otutab.py", tmpDir + "/otus.uc", 
                    ">", 
                    tmpDir + "/otu_table_prelim.txt"])
    rc.run_cmd_VSEARCH(cmd, logger, options.verbose)


    # Convert to biom
    logger.info("Converting classic tabular OTU into a BIOM format [BIOM]")
    try:
        os.remove(tmpDir + "/otu_table_prelim.biom")
    except OSError:
        pass
    cmd = " ".join([pd.BIOM, "convert", 
                    "-i", tmpDir + "/otu_table_prelim.txt", 
                    "-o", tmpDir + "/otu_table_prelim.biom", 
                    "--table-type=\"OTU table\""])
    rc.run_cmd(cmd, logger, options.verbose)


    # Classifying OTUs
    # http://sourceforge.net/projects/rdp-classifier/files/RDP_Classifier_TrainingData/ 
    logger.info("Assigning taxonomy [RDP Classifier]")
    cmd = " ".join(["java", "-jar", pd.RDP_CLASSIFIER_JAR, "classify", 
                    "-t", pd.UNITE_RETRAINED_DIR + "/rRNAClassifier.properties", 
                    "-o", options.outDir + "/assigned_taxonomy.txt", 
                    tmpDir + "/input_nr_otus_nonchimeras_relabelled.fasta"])
    rc.run_cmd(cmd, logger, options.verbose)


    # Reformatting RDP_CLASSIFIER output for biom
    logger.info("Reformatting RDP_Classifier output")
    cmd = " ".join(["python", EXE_DIR + "/reformatAssignedTaxonomy.py", 
                    "-i", options.outDir + "/assigned_taxonomy.txt" , 
                    "-o", options.outDir + "/assigned_taxonomy_reformatted_filtered.txt",
                    "-c", options.RDP_assignment_threshold])
    rc.run_cmd(cmd, logger, options.verbose)


    # Adding RDP_CLASSIFIER output to OTU table
    logger.info("Adding assignment to OTU table [BIOM]")
    try:
            os.remove(options.outDir + "/otu_table.biom")
    except OSError:
            pass
    cmd = " ".join([pd.BIOM, "add-metadata", 
                    "-i", tmpDir + "/otu_table_prelim.biom", 
                    "-o", options.outDir + "/otu_table.biom", 
                    "--observation-metadata-fp", options.outDir + "/assigned_taxonomy_reformatted_filtered.txt", 
                    "--observation-header", "OTUID,taxonomy,confidence", 
                    "--sc-separated", "taxonomy", 
                    "--float-fields", "confidence"])
    rc.run_cmd(cmd, logger, options.verbose)


    # Convert BIOM to TABLE
    logger.info("Converting OTU table with taxa assignment into a BIOM format [BIOM]")
    try:
        os.remove(options.outDir + "/otu_table.txt")
    except OSError:
        pass
    cmd = " ".join([pd.BIOM, "convert", 
                    "-i", options.outDir + "/otu_table.biom", 
                    "-o", options.outDir + "/otu_table.txt", 
                    "--header-key taxonomy",  
                    "-b"])
    rc.run_cmd(cmd, logger, options.verbose)


    # Make phylotyp table
    logger.info("Phylotyping OTU table")
    cmd = " ".join(["python", EXE_DIR + "/phylotype_biom.py", "-i", options.outDir + "/otu_table.biom", "-o", options.outDir + "/phylotype_table.txt"])
    rc.run_cmd(cmd, logger, options.verbose)

    try:
        os.remove(options.outDir + "/phylotype_table.biom")
    except OSError:
        pass
    cmd = " ".join([pd.BIOM, "convert",
                    "-i", options.outDir + "/phylotype_table.txt",
                    "-o", options.outDir + "/phylotype_table.biom",
                    "--table-type=\"OTU table\" --process-obs-metadata=\"taxonomy\""])
    rc.run_cmd(cmd, logger, options.verbose)


    # Move representative sequence file to outDir
    shutil.move(tmpDir + "/input_nr_otus_nonchimeras_relabelled.fasta", options.outDir + "/repseqs.fasta")


    # Remove tmp
    if options.remove:
        logger.info("Cleaning temporary directory")
        shutil.rmtree(tmpDir)


    # Final stats

    #############################
    # Import json formatted OTU #
    #############################

    def biomstats(BIOMFILE):
        import json
        jsondata = open(BIOMFILE)
        biom = json.load(jsondata)

        sampleSize = int(biom["shape"][1])
        otus = int(biom["shape"][0])

        taxonomies = []
        for i in range(len(biom["rows"])):
            taxonomies.append("; ".join(biom["rows"][i]["metadata"]["taxonomy"]))

        sampleids = []
        for i in range(len(biom["columns"])):
            sampleids.append(biom["columns"][i]["id"])

        import numpy as np

        # BIOM table into matrix
        matrix = np.zeros(shape=(otus, sampleSize))
        for i in biom["data"]:
            matrix[i[0], i[1]] = i[2]
        totalCount = matrix.sum()

        return totalCount, otus, sampleSize

    otu_reads_count, otu_count, otu_sample_count = biomstats(options.outDir + "/otu_table.biom")
    phylo_reads_count, phylo_count, phylo_sample_count = biomstats(options.outDir + "/phylotype_table.biom")

    outfile = open(options.outDir + "/summary_pipits_process.txt", "w")

    outfile.write("No.of reads after singletons and chimera removal: " + str(int(otu_reads_count)) + "\n")
    outfile.write("Number of OTUs:                                   " + str(otu_count) + "\n")
    outfile.write("Number of phylotypes:                             " + str(phylo_count) + "\n")
    outfile.write("Number of samples:                                " + str(otu_sample_count) + "\n")

    logger.info(tc.RED + "\tNumber of reads after singletons and chimera removal: " + str(int(otu_reads_count)) + tc.ENDC)
    logger.info(tc.RED + "\tNumber of OTUs:                                       " + str(otu_count) + tc.ENDC)
    logger.info(tc.RED + "\tNumber of phylotypes:                                 " + str(phylo_count) + tc.ENDC)
    logger.info(tc.RED + "\tNumber of samples:                                    " + str(otu_sample_count) + tc.ENDC)


    # Done!
    logger.info(tc.OKBLUE + "PIPITS_PROCESS ended successfully." + tc.ENDC)
    logger.info(tc.OKYELLOW + "Resulting files are in \"" + options.outDir + "\" directory" + tc.ENDC)
