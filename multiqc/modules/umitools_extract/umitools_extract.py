""" MultiQC module to parse output from UMI-tools """


import logging
import re
from collections import OrderedDict

from multiqc import config
from multiqc.modules.base_module import BaseMultiqcModule
from multiqc.plots import bargraph, beeswarm

# Initialise the logger
log = logging.getLogger(__name__)


class MultiqcModule(BaseMultiqcModule):
    """
    umitools module class, parses extract logs
    """

    def __init__(self):
        # Initialise the parent object
        super(MultiqcModule, self).__init__(
            name="UMI-tools extract",
            anchor="umitools_extract",
            href="https://github.com/CGATOxford/UMI-tools",
            info="contains tools for dealing with Unique Molecular Identifiers (UMIs)/(RMTs) and scRNA-Seq barcodes.",
            doi="10.1101/gr.209601.116",
        )

        # Find and load any umitools log files
        self.umitools_data = dict()
        for f in self.find_log_files("umitools_extract"):
            # Parse the log file for sample name and statistics
            input_fname, data = self.parse_logs(f)
            if data and len(data) > 1:
                # Clean the sample name
                f["s_name"] = self.clean_s_name(input_fname, f)
                # Log a warning if the log file matches an existing sample name
                if f["s_name"] in self.umitools_data:
                    log.debug("Duplicate sample name found! Overwriting: {}".format(f["s_name"]))
                # Store the data in the overall data dictionary
                self.umitools_data[f["s_name"]] = data
                # Add the log file information to the multiqc_sources.txt
                self.add_data_source(f)

        # Check the log files against the user supplied list of samples to ignore
        self.umitools_data = self.ignore_samples(self.umitools_data)

        # If no files are found, raise an exception
        if len(self.umitools_data) == 0:
            raise UserWarning

        # Log the number of reports found
        log.info("Found {} reports".format(len(self.umitools_data)))

        # Write parsed report data to a file
        self.write_data_file(self.umitools_data, "multiqc_umitools")

        # write data to the general statistics table
        self.umitools_extract_general_stats_table()

        # add a section with a extracted reads plot to the report
        self.add_section(
            name="Extracted Reads",
            anchor="umitools-extract-plot",
            description="This plot shows the number of extracted reads.",
            plot=self.umitools_extraction_barplot(),
        )


    def parse_logs(self, f):
        # Check this is a extract log
        if "# output generated by extract" not in f["f"]:
            log.debug(f"Skipping as not an extract log: {f['fn']}")
            return None, None

        # Get the s_name from the input file if possible
        # stdin : <_io.TextIOWrapper name='M18-39155_T1.Aligned.sortedByCoord.out.bam' mode='r' encoding='UTF-8'>
        s_name_re = r"stdin\s+:\s+<_io\.TextIOWrapper name='([^\']+)'"
        s_name_match = re.search(s_name_re, f["f"])
        if s_name_match:
            s_name = s_name_match.group(1)
        else:
            s_name = f["s_name"]

        # Initialise a dictionary to hold the data from this log file
        data = {}

        # Search for values using regular expressions
        regexes = {
            "input_reads": r"INFO Input Reads: (\d+)",
            "output_reads": r"INFO Reads output: (\d+)",
            "filtered_reads": r"INFO Filtered cell barcode: (\d+)",
        }
        for key, regex in regexes.items():
            re_matches = re.search(regex, f["f"])
            if re_matches:
                data[key] = float(re_matches.group(1))

        # calculate a few simple supplementary stats
        try:
            data["percent_extracted_reads"] = round(((data["output_reads"] / data["input_reads"]) * 100.0), 2)
        except (KeyError, ZeroDivisionError):
            pass

        return s_name, data

    def umitools_extract_general_stats_table(self):
        """Take the parsed stats from the umitools report and add it to the
        basic stats table at the top of the report"""

        headers = OrderedDict()
        headers["percent_extracted_reads"] = {
            "title": "% Extracted Reads",
            "description": "% processed reads extracted with cell barcode",
            "max": 100,
            "min": 0,
            "suffix": "%",
            "scale": "RdYlGn",
        }
        self.general_stats_addcols(self.umitools_data, headers)

    def umitools_extraction_plot(self):
        """Generate a plot with the extracted reads"""

        # Specify the order of the different possible categories
        keys = OrderedDict()
        keys["output_reads"] = {"color": "#7fc97f", "name": "Reads remaining"}
        keys["filtered_reads"] = {"color": "#fdc086", "name": "Reads removed"}

        # Config for the plot
        config = {
            "id": "umitools_extract_barplot",
            "title": "UMI-tools: Extraction Counts",
            "ylab": "# Reads",
            "cpswitch_counts_label": "Number of Reads",
        }

        return bargraph.plot(self.umitools_data, keys, config)
