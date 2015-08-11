#!/usr/bin/env python
###############################################################################
# Copyright (c) 2011-2013, Pacific Biosciences of California, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of Pacific Biosciences nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE.  THIS SOFTWARE IS PROVIDED BY PACIFIC BIOSCIENCES AND ITS
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL PACIFIC BIOSCIENCES OR
# ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

# Author:Yuan Li
"""This scripts defines functions for parsing PBAlignRunner options."""

from __future__ import absolute_import
import argparse
import logging
from copy import copy
import json
import sys

from pbcommand.models import FileTypes, SymbolTypes, get_pbparser
from pbcommand.common_options import add_resolved_tool_contract_option, \
    add_debug_option


class Constants(object):
    TOOL_ID = "pbalign.tasks.pbalign"
    INPUT_FILE_TYPE = FileTypes.DS_SUBREADS
    OUTPUT_FILE_TYPE = FileTypes.DS_ALIGN
    OUTPUT_FILE_NAME = "aligned.subreads.xml"
    ALGORITHM_OPTIONS_ID = "pbalign.task_options.algorithm_options"
    MIN_ACCURACY_ID = "pbalign.task_options.min_accuracy"
    MIN_LENGTH_ID = "pbalign.task_options.min_length"
    CONCORDANT_ID = "pbalign.task_options.concordant"
    DRIVER_EXE = "pbalign --resolved-tool-contract "
    VERSION = "3.0"
    PARSER_DESC = """\
Mapping PacBio sequences to references using an algorithm selected from a
selection of supported command-line alignment algorithms. Input can be a
fasta, pls.h5, bas.h5 or ccs.h5 file or a fofn (file of file names). Output
can be in CMP.H5, SAM or BAM format. If output is BAM format, aligner can
only be blasr and QVs will be loaded automatically."""

# The first candidate 'blasr' is the default.
ALGORITHM_CANDIDATES = ('blasr', 'bowtie', 'gmap')

# The first candidate 'randombest' is the default.
HITPOLICY_CANDIDATES = ('randombest', 'allbest', 'random', 'all', 'leftmost')

# The first candidate 'aligner' is the default.
SCOREFUNCTION_CANDIDATES = ('alignerscore', 'editdist',
                            #'blasrscore', 'userscore')
                            'blasrscore')
DEFAULT_METRICS = ("DeletionQV", "DeletionTag", "InsertionQV",
                   "MergeQV", "SubstitutionQV")

# Default values of arguments
DEFAULT_OPTIONS = {"regionTable": None,
                   "configFile": None,
                   # Choose an aligner
                   "algorithm": ALGORITHM_CANDIDATES[0],
                   # Aligner options
                   "maxHits": 10,
                   "minAnchorSize": 12,
                   "noSplitSubreads": False,
                   "concordant": False,
                   "algorithmOptions": None,
                   "useccs": None,
                   # Filter options
                   "maxDivergence": 30.0,
                   "minAccuracy": 70.0,
                   "minLength": 50,
                   #"scoreFunction": SCOREFUNCTION_CANDIDATES[0],
                   "scoreCutoff": None,
                   "hitPolicy": HITPOLICY_CANDIDATES[0],
                   "filterAdapterOnly": False,
                   # Cmp.h5 writer options
                   "readType": "standard",
                   "forQuiver": False,
                   "loadQVs": False,
                   "byread": False,
                   "metrics": str(",".join(DEFAULT_METRICS)),
                   # Miscellaneous options
                   "nproc": 8,
                   "seed": 1,
                   "tmpDir": "/scratch"}

def constructOptionParser(parser):
    """
    Add PBAlignRunner arguments to the parser.
    """
    # save reference to PbParser
    p = parser
    tcp = p.tool_contract_parser
    parser = parser.arg_parser.parser
    #parser.argument_default = argparse.SUPPRESS
    parser.formatter_class = argparse.RawTextHelpFormatter
    parser.add_argument("--verbose", action="store_true")
    add_debug_option(parser)

    # Optional input.
    input_group = parser.add_argument_group("Optional input arguments")
    input_group.add_argument("--regionTable",
                        dest="regionTable",
                        type=str,
                        default=None,
                        action="store",
                        help="Specify a region table for filtering reads.")

    input_group.add_argument("--configFile",
                        dest="configFile",
                        default=None,
                        type=str,
                        action="store",
                        help="Specify a set of user-defined argument values.")

    helpstr = "When input reads are in fasta format and output is a cmp.h5\n" + \
              "this option can specify pls.h5 or bas.h5 or \n" + \
              "FOFN files from which pulse metrics can be loaded for Quiver."
    input_group.add_argument("--pulseFile",
                        dest="pulseFile",
                        default=None,
                        type=str,
                        action="store",
                        help=helpstr)

    # Chose an aligner.
    align_group = parser.add_argument_group("Alignment options")
    helpstr = "Select an aligorithm from {0}.\n".format(ALGORITHM_CANDIDATES)
    helpstr += "Default algorithm is {0}.".format(DEFAULT_OPTIONS["algorithm"])
    align_group.add_argument("--algorithm",
                        dest="algorithm",
                        type=str,
                        action="store",
                        choices=ALGORITHM_CANDIDATES,
                        default=ALGORITHM_CANDIDATES[0],
                        help=helpstr)

    # Aligner options.
    helpstr = "The maximum number of matches of each read to the \n" + \
              "reference sequence that will be evaluated. Default\n" + \
              "value is {0}.".format(DEFAULT_OPTIONS["maxHits"])
    align_group.add_argument("--maxHits",
                        dest="maxHits",
                        type=int,
                        default=None,  # Set as None instead of a real number.
                        action="store",
                        help=helpstr)

    helpstr = "The minimum anchor size defines the length of the read\n" + \
              "that must match against the reference sequence. Default\n" + \
              "value is {0}.".format(DEFAULT_OPTIONS["minAnchorSize"])
    align_group.add_argument("--minAnchorSize",
                        dest="minAnchorSize",
                        type=int,
                        default=None,  # Set as None to avoid conflicts with
                                       # --algorithmOptions
                        action="store",
                        help=helpstr)

    # Aligner options: Use ccs or not?
    helpstr = "Map the ccsSequence to the genome first, then align\n" + \
              "subreads to the interval that the CCS reads mapped to.\n" + \
              "  useccs: only maps subreads that span the length of\n" + \
              "          the template.\n" + \
              "  useccsall: maps all subreads.\n" + \
              "  useccsdenovo: maps ccs only."
    align_group.add_argument("--useccs",
                        type=str,
                        choices=["useccs", "useccsall", "useccsdenovo"],
                        action="store",
                        default=None,
                        help=helpstr)

    helpstr = "Do not split reads into subreads even if subread \n" + \
              "regions are available. Default value is {0}."\
              .format(DEFAULT_OPTIONS["noSplitSubreads"])
    align_group.add_argument("--noSplitSubreads",
                        dest="noSplitSubreads",
                        default=DEFAULT_OPTIONS["noSplitSubreads"],
                        action="store_true",
                        help=helpstr)

    helpstr = "Map subreads of a ZMW to the same genomic location.\n"
    align_group.add_argument("--concordant",
                        dest="concordant",
                        default=DEFAULT_OPTIONS["concordant"],
                        action="store_true",
                        help=helpstr)
    tcp.add_boolean(Constants.CONCORDANT_ID, "concordant",
        default=DEFAULT_OPTIONS["concordant"],
        name="Concordant alignment",
        description="Map subreads of a ZMW to the same genomic location")

    helpstr = "Number of threads. Default value is {v}."\
              .format(v=DEFAULT_OPTIONS["nproc"])
    align_group.add_argument("--nproc",
                        type=int,
                        dest="nproc",
                        default=DEFAULT_OPTIONS["nproc"],
                        #default=15,
                        action="store",
                        help=helpstr)

    align_group.add_argument("--algorithmOptions",
                        type=str,
                        dest="algorithmOptions",
                        default=None,
                        action="append",
                        help="Pass alignment options through.")
    tcp.add_str(Constants.ALGORITHM_OPTIONS_ID, "algorithmOptions",
        default="", #DEFAULT_OPTIONS["algorithmOptions"],
        name="Algorithm options",
        description="List of space-separated arguments passed to BLASR (etc.)")

    # Filtering criteria and hit policy.
    filter_group = parser.add_argument_group("Filter criteria options")
    helpstr = "The maximum allowed percentage divergence of a read \n" + \
              "from the reference sequence. Default value is {0}." \
              .format(DEFAULT_OPTIONS["maxDivergence"])
    filter_group.add_argument("--maxDivergence",
                        dest="maxDivergence",
                        type=float,
                        default=DEFAULT_OPTIONS["maxDivergence"],
                        #default=30,
                        action="store",
                        help=helpstr)

    helpstr = "The minimum percentage accuracy of alignments that\n" + \
              "will be evaluated. Default value is {v}." \
              .format(v=DEFAULT_OPTIONS["minAccuracy"])
    filter_group.add_argument("--minAccuracy",
                        dest="minAccuracy",
                        type=float,
                        default=DEFAULT_OPTIONS["minAccuracy"],
                        #default=70,
                        action="store",
                        help=helpstr)
    tcp.add_float(Constants.MIN_ACCURACY_ID, "minAccuracy",
        default=DEFAULT_OPTIONS["minAccuracy"],
        name="Min. accuracy",
        description="Minimum required alignment accuracy (percent)")

    helpstr = "The minimum aligned read length of alignments that\n" + \
              "will be evaluated. Default value is {v}." \
              .format(v=DEFAULT_OPTIONS["minLength"])
    filter_group.add_argument("--minLength",
                        dest="minLength",
                        type=int,
                        default=DEFAULT_OPTIONS["minLength"],
                        action="store",
                        help=helpstr)
    tcp.add_int(Constants.MIN_LENGTH_ID, "minLength",
        default=DEFAULT_OPTIONS["minLength"],
        name="Min. length",
        description="Minimum required alignment length")

    #helpstr = "Specify a score function for evaluating alignments.\n"
    #helpstr += "  alignerscore : aligner's score in the SAM tag 'as'.\n"
    #helpstr += "  editdist     : edit distance between read and reference.\n"
    #helpstr += "  blasrscore   : blasr's default score function.\n"
    #helpstr += "Default value is {0}.".format(DEFAULT_OPTIONS["scoreFunction"])
    #filter_group.add_argument("--scoreFunction",
    #                    dest="scoreFunction",
    #                    type=str,
    #                    choices=SCOREFUNCTION_CANDIDATES,
    #                    default=DEFAULT_OPTIONS["scoreFunction"],
    #                    action="store",
    #                    help=helpstr)
    #"  userscore    : user-defined score matrix (by -scoreMatrix).\n")
    #parser.add_argument("--scoreMatrix",
    #                    dest="scoreMatrix",
    #                    type=str,
    #                    default=None,
    #                    help=
    #                    "Specify a user-defined score matrix for "
    #                    "scoring reads.The matrix\n"+\
    #                    "is in the format\n"
    #                    "    ACGTN\n"
    #                    "  A abcde\n"
    #                    "  C fghij\n"
    #                    "  G klmno\n"
    #                    "  T pqrst\n"
    #                    "  N uvwxy\n"
    #                    ". The values a...y should be input as a "
    #                    "quoted space separated\n"
    #                    "string: "a b c ... y". Lower scores are better,"
    #                    "so matches\n"
    #                    "should be less than mismatches e.g. a,g,m,s "
    #                    "= -5 (match),\n"
    #                    "mismatch = 6.\n")

    filter_group.add_argument("--scoreCutoff",
                        dest="scoreCutoff",
                        type=int,
                        default=None,
                        action="store",
                        help="The worst score to output an alignment.\n")

    helpstr = "Specify a policy for how to treat multiple hit\n" + \
           "  random    : selects a random hit.\n" + \
           "  all       : selects all hits.\n" + \
           "  allbest   : selects all the best score hits.\n" + \
           "  randombest: selects a random hit from all best score hits.\n" + \
           "  leftmost  : selects a hit which has the best score and the\n" + \
           "              smallest mapping coordinate in any reference.\n" + \
           "Default value is {v}.".format(v=DEFAULT_OPTIONS["hitPolicy"])
    filter_group.add_argument("--hitPolicy",
                        dest="hitPolicy",
                        type=str,
                        choices=HITPOLICY_CANDIDATES,
                        default=DEFAULT_OPTIONS["hitPolicy"],
                        action="store",
                        help=helpstr)

    helpstr = "If specified, do not report adapter-only hits using\n" + \
              "annotations with the reference entry."
    filter_group.add_argument("--filterAdapterOnly",
                        dest="filterAdapterOnly",
                        default=DEFAULT_OPTIONS["filterAdapterOnly"],
                        action="store_true",
                        help=helpstr)

    # Output.
    cmph5_group = parser.add_argument_group("Options for cmp.h5")
    helpstr = "Specify the ReadType attribute in the cmp.h5 output.\n" + \
              "Default value is {v}.".format(v=DEFAULT_OPTIONS["readType"])
    cmph5_group.add_argument("--readType",
                        dest="readType",
                        type=str,
                        action="store",
                        default=DEFAULT_OPTIONS["readType"],
                        help=argparse.SUPPRESS)
                        #help=helpstr)

    helpstr = "The output cmp.h5 file which will be sorted, loaded\n" + \
              "with pulse QV information, and repacked, so that it \n" + \
              "can be consumed by quiver directly. This requires\n" + \
              "the input file to be in PacBio bas/pls.h5 format,\n" + \
              "and --useccs must be None. Default value is False."
    cmph5_group.add_argument("--forQuiver",
                        dest="forQuiver",
                        action="store_true",
                        default=DEFAULT_OPTIONS["forQuiver"],
                        help=helpstr)

    helpstr = "Similar to --forQuiver, the only difference is that \n" + \
              "--useccs can be specified. Default value is False."
    cmph5_group.add_argument("--loadQVs",
                        dest="loadQVs",
                        action="store_true",
                        default=DEFAULT_OPTIONS["loadQVs"],
                        help=helpstr)

    helpstr = "Load pulse information using -byread option instead\n" + \
              "of -bymetric. Only works when --forQuiver or \n" + \
              "--loadQVs are set. Default value is False."
    cmph5_group.add_argument("--byread",
                        dest="byread",
                        action="store_true",
                        default=DEFAULT_OPTIONS["byread"],
                        help=helpstr)

    helpstr = "Load the specified (comma-delimited list of) metrics\n" + \
              "instead of the default metrics required by quiver.\n" + \
              "This option only works when --forQuiver  or \n" + \
              "--loadQVs are set. Default: {m}".\
              format(m=DEFAULT_OPTIONS["metrics"])
    cmph5_group.add_argument("--metrics",
                        dest="metrics",
                        type=str,
                        action="store",
                        default=DEFAULT_OPTIONS["metrics"],
                        help=helpstr)

    # Miscellaneous.
    misc_group = parser.add_argument_group("Miscellaneous options")
    helpstr = "Initialize the random number generator with a none-zero \n" + \
              "integer. Zero means that current system time is used.\n" + \
              "Default value is {v}.".format(v=DEFAULT_OPTIONS["seed"])
    misc_group.add_argument("--seed",
                        dest="seed",
                        type=int,
                        default=DEFAULT_OPTIONS["seed"],
                        action="store",
                        help=helpstr)

    helpstr = "Specify a directory for saving temporary files.\n" + \
              "Default is {v}.".format(v=DEFAULT_OPTIONS["tmpDir"])
    misc_group.add_argument("--tmpDir",
                        dest="tmpDir",
                        type=str,
                        action="store",
                        default=DEFAULT_OPTIONS["tmpDir"],
                        help=helpstr)

    # Keep all temporary & intermediate files.
    misc_group.add_argument("--keepTmpFiles",
                        dest="keepTmpFiles",
                        action="store_true",
                        default=False,
                        help=argparse.SUPPRESS)
    return parser


def importConfigOptions(options):
    """
    Import options from options.configFile if the file exists, and
    overwrite a copy of the incoming options with options imported
    from the config file. Finally, return the new options and an
    info message.
    """
    newOptions = copy(options)
    # No config file exists.
    if 'configFile' not in options or options.configFile is None:
        return newOptions, ""

    # There exists a config file
    optionsDictView = vars(newOptions)
    configFile = options.configFile
    infoMsg = "ConfigParser: Import options from a config file {0}: "\
              .format(configFile)
    # The following arguments are defined in PBToolRunner, and may
    # not exist in the input options (if the input options is parsed
    # by a parser created in constructOptionParser).
    specialArguments = ("--version", "--configFile", "--verbose",
                        "--debug", "--profile", "-v", "-vv", "-vvv",
                        "--keepTmpFiles")
    try:
        with open(configFile, 'r') as cf:
            for line in cf:
                line = line.strip()
                errMsg = ""
                # First parse special arguments and comments
                if (line.startswith("#") or line == "" or
                        line in specialArguments):
                    pass
                else:  # Parse binary arguments
                    try:
                        k, v = line.split("=")
                        k = k.lstrip().lstrip('-').strip()
                        v = v.strip().strip('\"').strip('\'')
                    except ValueError as e:
                        errMsg = "ConfigParser: could not find '=' when " + \
                                 "parsing {0}.".format(line)
                        raise ValueError(errMsg)
                    # Always use options' values from the configFile.
                    if k not in optionsDictView:
                        errMsg = "{k} is an invalid option.".format(k=k)
                        raise ValueError(errMsg)
                    else:
                        infoMsg += "{k}={v}, ".format(k=k, v=v)
                        optionsDictView[k] = v
    except IOError as e:
        errMsg = "ConfigParser: Could not open a config file {0}.\n".\
                 format(configFile)
        raise IOError(errMsg + str(e))
    return newOptions, infoMsg


def importDefaultOptions(parsedOptions, additionalDefaults=DEFAULT_OPTIONS):
    """Import default options and return (update_options, an_info_message).

    After parsing the arguments and resolving algorithmOptions, we need
    to patch the default pbalign options, if they have not been overwritten
    on the command-line nor in the config file nor within algorithmOptions.

    """
    newOptions = copy(parsedOptions)
    infoMsg = "Importing default options: "
    optionsDictView = vars(newOptions)
    for k, v in additionalDefaults.iteritems():
        if (k not in optionsDictView) or (optionsDictView[k] is None):
            infoMsg += "{k}={v}, ".format(k=optionsDictView[k], v=v)
            optionsDictView[k] = v
    return newOptions, infoMsg.rstrip(', ')


class _ArgParser(argparse.ArgumentParser):
    """
    Substitute for the standard argument parser, where parse_args is
    extended to facilitate the use of config files.
    """
    def parse_args(self, args=None, namespace=None):
        options = super(_ArgParser, self).parse_args(args=args,
            namespace=namespace)
    
        # Import options from the specified config file, if it exists.
        configOptions, infoMsg = importConfigOptions(options)
    
        # Parse argumentList for the second time in order to
        # overwrite config options with options in argumentList.
        newOptions = copy(configOptions)
        newOptions.algorithmOptions = None
        newOptions = super(_ArgParser, self).parse_args(namespace=newOptions,
            args=args)
    
        # Overwrite config algorithmOptions if it is specified in argumentList
        if newOptions.algorithmOptions is None:
            if configOptions.algorithmOptions is not None:
                newOptions.algorithmOptions = configOptions.algorithmOptions
        else:
            newOptions.algorithmOptions = \
                " ".join(newOptions.algorithmOptions)   

        # FIXME gross hack to work around the problem of passing this
        # parameter from a resolved tool contract
        def unquote(s):
            if s[0] in ["'", '"'] and s[-1] in ["'", '"']:
                return s[1:-1]
            return s
        if newOptions.algorithmOptions is not None:
            newOptions.algorithmOptions = unquote(newOptions.algorithmOptions)
 
        # Return the updated options and an info message.
        return newOptions #parser, newOptions, infoMsg

def get_contract_parser(C=Constants):
    """
    Create and populate the combined tool contract/argument parser.  This
    method can optionally be overridden with a different Constants object for
    defining additional tasks (e.g. CCS alignment).
    """
    resources = ()
    p = get_pbparser(
        tool_id=C.TOOL_ID,
        version=C.VERSION,
        name=C.TOOL_ID,
        description=C.PARSER_DESC,
        driver_exe=C.DRIVER_EXE,
        nproc=SymbolTypes.MAX_NPROC)
    p.arg_parser.parser = _ArgParser(
        version=C.VERSION,
        description=C.PARSER_DESC,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Required options: inputs and outputs.
    p.add_input_file_type(C.INPUT_FILE_TYPE, "inputFileName",
        "Subread DataSet", "SubreadSet or unaligned .bam")
    p.add_input_file_type(FileTypes.DS_REF, "referencePath",
        "ReferenceSet", "Reference DataSet or FASTA file")
    p.add_output_file_type(C.OUTPUT_FILE_TYPE, "outputFileName",
        name="XML DataSet",
        description="Output AlignmentSet file",
        default_name=C.OUTPUT_FILE_NAME)
    constructOptionParser(p)
    p.arg_parser.parser.add_argument(
        "--profile", action="store_true",
        help="Print runtime profile at exit")
    return p

def resolved_tool_contract_to_args(resolved_tool_contract):
    rtc = resolved_tool_contract
    p = get_contract_parser().arg_parser.parser
    args = [
        rtc.task.input_files[0],
        rtc.task.input_files[1],
        rtc.task.output_files[0],
        "--nproc", str(resolved_tool_contract.task.nproc),
        "--minAccuracy", str(rtc.task.options[Constants.MIN_ACCURACY_ID]),
        "--minLength", str(rtc.task.options[Constants.MIN_LENGTH_ID]),
    ]
    if rtc.task.options[Constants.ALGORITHM_OPTIONS_ID]:
        # FIXME this is gross: if I don't quote the options, the parser chokes;
        # if I do quote them, the quotes get propagated, so I have to strip
        # them off later
        args.extend([
            "--algorithmOptions=\"%s\"" %
            rtc.task.options[Constants.ALGORITHM_OPTIONS_ID],
        ])
    return p.parse_args(args)
